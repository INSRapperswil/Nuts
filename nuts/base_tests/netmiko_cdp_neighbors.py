"""Query CDP neighbors of a device."""
from typing import Callable, Dict, Any

import pytest
from nornir.core.filter import F
from nornir.core.task import MultiResult, AggregatedResult, Result
from nornir_netmiko import netmiko_send_command

from nuts.helpers.filters import filter_hosts
from nuts.helpers.result import NutsResult, AbstractResultExtractor
from nuts.context import NornirNutsContext


class CdpNeighborsExtractor(AbstractResultExtractor):
    def transform_result(
        self, general_result: AggregatedResult
    ) -> Dict[str, NutsResult]:
        return self.map_host_to_nutsresult(general_result)

    def single_transform(self, host_results: MultiResult) -> Dict[str, Dict[str, Any]]:
        assert host_results[0].result is not None
        return {
            neighbor["destination_host"]: neighbor
            for neighbor in host_results[0].result
        }


class CdpNeighborsContext(NornirNutsContext):
    def nuts_task(self) -> Callable[..., Result]:
        return netmiko_send_command

    def nuts_arguments(self) -> Dict[str, Any]:
        return {"command_string": "show cdp neighbors detail", "use_textfsm": True}

    def nornir_filter(self) -> F:
        return filter_hosts(self.nuts_parameters["test_data"])

    def nuts_extractor(self) -> CdpNeighborsExtractor:
        return CdpNeighborsExtractor(self)


CONTEXT = CdpNeighborsContext


class TestNetmikoCdpNeighbors:
    @pytest.mark.nuts("remote_host")
    def test_remote_host(self, single_result, remote_host):
        assert remote_host in single_result.result

    @pytest.mark.nuts("remote_host,local_port")
    def test_local_port(self, single_result, remote_host, local_port):
        assert single_result.result[remote_host]["local_port"] == local_port

    @pytest.mark.nuts("remote_host,remote_port")
    def test_remote_port(self, single_result, remote_host, remote_port):
        assert single_result.result[remote_host]["remote_port"] == remote_port

    @pytest.mark.nuts("remote_host,management_ip")
    def test_management_ip(self, single_result, remote_host, management_ip):
        assert single_result.result[remote_host]["management_ip"] == management_ip
