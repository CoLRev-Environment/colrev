import colrev.package_manager
from .prospero import ProsperoSearchSource
from colrev.package_manager import EndpointType

colrev.package_manager.register_package_endpoint(
    package="colrev.prospero",
    endpoint="colrev.prospero",
    endpoint_type=EndpointType.search_source,
    implementation=ProsperoSearchSource,
)

"""Package for colrev.prospero."""

__author__ = "Ammar Al-Balkhi, Phuc Tran, Olha Komashevska"
__email__ = "ammar.al-balkhi@stud.uni-bamberg.de, tra-thien-phuc.tran@stud.uni-bamberg.de, olha.komashevska@stud.uni-bamberg.de"
