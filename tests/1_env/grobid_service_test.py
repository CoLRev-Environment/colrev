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
    client = mocker.Mock()
    client.is_available.side_effect = [False, True]
    grobid_client = mocker.patch(
        "colrev.env.grobid_service.grobid_tei.GrobidClient", return_value=client
    )
    sleep = mocker.patch("colrev.env.grobid_service.time.sleep")
    mocker.patch.object(service, "_ensure_correct_version")
    mocker.patch("colrev.env.grobid_service.time.monotonic", side_effect=[0.0, 0.0])

    assert service.check_grobid_availability(wait=True, timeout=2) is True

    assert grobid_client.call_count == 2
    assert client.is_available.call_count == 2
    sleep.assert_called_once_with(1)


def test_availability_timeout_raises_connection_error(mocker: Any) -> None:
    service = _service()
    client = mocker.Mock()
    client.is_available.return_value = False
    grobid_client = mocker.patch(
        "colrev.env.grobid_service.grobid_tei.GrobidClient", return_value=client
    )
    mocker.patch("colrev.env.grobid_service.time.monotonic", side_effect=[0.0, 0.0])

    with pytest.raises(requests.exceptions.ConnectionError, match="within 0 seconds"):
        service.check_grobid_availability(wait=True, timeout=0)

    grobid_client.assert_called_once_with(
        service_url=service.GROBID_URL,
        timeout=service.HEALTHCHECK_TIMEOUT,
        skip_version=True,
    )
    client.is_available.assert_called_once_with()


def test_version_check_uses_grobid_tei_client(mocker: Any) -> None:
    service = _service()
    client = mocker.Mock()
    client.version.return_value = "0.9.0"
    grobid_client = mocker.patch(
        "colrev.env.grobid_service.grobid_tei.GrobidClient", return_value=client
    )

    service._ensure_correct_version()

    grobid_client.assert_called_once_with(
        service_url=service.GROBID_URL,
        timeout=10,
        skip_version=True,
    )
    client.version.assert_called_once_with()


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
    check_availability = mocker.patch.object(
        service, "check_grobid_availability", side_effect=[False, True]
    )
    client = mocker.Mock()
    client.containers.run.side_effect = docker.errors.APIError(
        "Bind for 0.0.0.0:8070 failed: port is already allocated"
    )
    mocker.patch("colrev.env.grobid_service.docker.from_env", return_value=client)

    service.start()

    client.containers.run.assert_called_once()
    assert check_availability.call_args_list[1].kwargs == {
        "wait": True,
        "timeout": service.STARTUP_TIMEOUT,
    }
    client.close.assert_called_once()
