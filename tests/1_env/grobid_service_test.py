"""Tests for GROBID service startup and readiness handling."""

from typing import Any

import docker
import pytest
import requests

import colrev.env.grobid_service


def _service() -> colrev.env.grobid_service.GrobidService:
    """Create a service instance without running its Docker startup logic."""
    return colrev.env.grobid_service.GrobidService.__new__(
        colrev.env.grobid_service.GrobidService
    )


def test_availability_waits_for_service_to_become_alive(
    mocker: Any,
) -> None:
    service = _service()
    get = mocker.patch(
        "colrev.env.grobid_service.requests.get",
        side_effect=[mocker.Mock(text="false"), mocker.Mock(text="true")],
    )
    sleep = mocker.patch("colrev.env.grobid_service.time.sleep")
    mocker.patch.object(service, "_ensure_correct_version")
    mocker.patch("colrev.env.grobid_service.time.monotonic", side_effect=[0.0, 0.0])

    assert service.check_grobid_availability(wait=True, timeout=2) is True

    assert get.call_count == 2
    sleep.assert_called_once_with(1)


def test_availability_timeout_raises_connection_error(mocker: Any) -> None:
    service = _service()
    get = mocker.patch(
        "colrev.env.grobid_service.requests.get", return_value=mocker.Mock(text="false")
    )
    mocker.patch("colrev.env.grobid_service.time.monotonic", side_effect=[0.0, 0.0])

    with pytest.raises(requests.exceptions.ConnectionError, match="within 0 seconds"):
        service.check_grobid_availability(wait=True, timeout=0)

    get.assert_called_once()


def test_start_stops_container_when_readiness_times_out(mocker: Any) -> None:
    service = _service()
    mocker.patch.object(
        service,
        "check_grobid_availability",
        side_effect=[False, requests.exceptions.ConnectionError("not ready")],
    )
    container = mocker.Mock()
    client = mocker.Mock()
    client.containers.run.return_value = container
    mocker.patch("colrev.env.grobid_service.docker.from_env", return_value=client)

    with pytest.raises(requests.exceptions.ConnectionError, match="not ready"):
        service.start()

    container.stop.assert_called_once_with(timeout=10)
    client.close.assert_called_once()


def test_start_waits_for_service_when_port_is_already_allocated(mocker: Any) -> None:
    service = _service()
    mocker.patch.object(service, "check_grobid_availability", side_effect=[False, True])
    client = mocker.Mock()
    client.containers.run.side_effect = docker.errors.APIError(
        "Bind for 0.0.0.0:8070 failed: port is already allocated"
    )
    mocker.patch("colrev.env.grobid_service.docker.from_env", return_value=client)

    service.start()

    client.containers.run.assert_called_once()
    assert service.check_grobid_availability.call_args_list[1].kwargs == {
        "wait": True,
        "timeout": service.STARTUP_TIMEOUT,
    }
    client.close.assert_called_once()
