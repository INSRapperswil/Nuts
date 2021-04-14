from unittest.mock import Mock, ANY

import pytest
from nornir.core.plugins.connections import ConnectionPluginRegister
from nornir.core.plugins.inventory import InventoryPluginRegister
from nornir.core.plugins.runners import RunnersPluginRegister

from pytest_nuts.context import NornirNutsContext, NutsSetupError, NutsContext
from tests.helpers.shared import YAML_EXTENSION


class CustomNornirNutsContext(NornirNutsContext):
    def __init__(self, nuts_parameters):
        super().__init__(nuts_parameters)
        self.test_filter = None
        self.test_task = lambda task: task.host.name
        self.test_arguments = {}

    def nuts_arguments(self):
        return self.test_arguments

    def nuts_task(self):
        return self.test_task

    def nornir_filter(self):
        return self.test_filter


@pytest.fixture
def nornir_instance():
    return Mock()


@pytest.fixture
def nornir_nuts_ctx(nornir_instance):
    context = CustomNornirNutsContext({})
    context.nornir = nornir_instance
    return context


class TestNornirNutsContextTestExecutionField:
    def test_test_execution_not_existing(self):
        context = NutsContext({})
        assert context.nuts_arguments() == {}

    def test_test_execution_exists_but_empty(self):
        context = NutsContext({"test_execution": None})
        assert context.nuts_arguments() == {}

    def test_test_execution_contains_data(self):
        context = NutsContext({"test_execution": {"count": 42, "ref": 23}})
        assert context.nuts_arguments() == {"count": 42, "ref": 23}


class TestNornirNutsContextGeneralResult:
    def test_raises_nuts_setup_error_if_nornir_is_not_defined(self):
        with pytest.raises(NutsSetupError):
            ctx = CustomNornirNutsContext({})

            ctx.general_result()

    def test_filters_inventory_based_on_nornir_filter(self, nornir_nuts_ctx, nornir_instance):
        nornir_nuts_ctx.test_filter = Mock()

        nornir_nuts_ctx.general_result()

        nornir_instance.filter.assert_called_with(nornir_nuts_ctx.test_filter)

    def test_calls_run_on_filtered_inventory(self, nornir_nuts_ctx, nornir_instance):
        filtered_inventory = Mock()
        nornir_instance.filter.return_value = filtered_inventory
        nornir_nuts_ctx.test_filter = Mock()

        nornir_nuts_ctx.general_result()

        assert filtered_inventory.run.called

    def test_passes_nuts_arguments_to_nornir(self, nornir_nuts_ctx, nornir_instance):
        nornir_nuts_ctx.test_arguments = {"test": "test123", "test2": "test456"}

        nornir_nuts_ctx.general_result()

        nornir_instance.run.assert_called_with(task=ANY, test="test123", test2="test456")

    def test_runs_nuts_task_on_inventory(self, nornir_nuts_ctx, nornir_instance):
        nornir_nuts_ctx.general_result()

        nornir_instance.run.assert_called_with(task=nornir_nuts_ctx.nuts_task())

    def test_returns_nornir_result(self, nornir_nuts_ctx, nornir_instance):
        nornir_results = Mock()
        nornir_instance.run.return_value = nornir_results

        result = nornir_nuts_ctx.general_result()

        assert result == nornir_results


@pytest.fixture
def nr_wrapper():
    """
    Cleanup Nornir's PluginRegisters.

    This is necessary as InitNornir is initiated for every test case, but the PluginRegisters are (somehow) shared.
    This results in a PluginAlreadyRegistered Exception as the plugins are registered multiple times.
    """
    yield None
    ConnectionPluginRegister.deregister_all()
    InventoryPluginRegister.deregister_all()
    RunnersPluginRegister.deregister_all()


@pytest.fixture
def default_nr_init(testdir):
    """Create initial Nornir files and expose the location as nornir_config_file fixture."""
    hosts_path = testdir.tmpdir.join(f"hosts{YAML_EXTENSION}")
    config = f"""inventory:
                          plugin: SimpleInventory
                          options:
                              host_file: {hosts_path}"""
    arguments = {
        "nr-config": config,
        "hosts": """
            R1:
              hostname: 10.20.0.31
            R2:
              hostname: 10.20.0.32""",
    }
    testdir.makefile(YAML_EXTENSION, **arguments)
    nr_path = testdir.tmpdir.join(f"nr-config{YAML_EXTENSION}")
    conf_test = f"""
          from nornir.core import Task
          import pytest

          @pytest.fixture(scope="session")
          def nornir_config_file():
              return r"{nr_path}"
                  """
    testdir.makeconftest(conf_test)


@pytest.mark.usefixtures("default_nr_init", "nr_wrapper")
class TestNornirNutsContextIntegration:
    def test_fails_if_no_task_is_defined(self, testdir):
        testdir.makepyfile(
            basic_task="""
            from pytest_nuts.context import NornirNutsContext


            class FailingNornirNutsContext(NornirNutsContext):
                pass

            CONTEXT = FailingNornirNutsContext

            class TestBasicTask:
                def test_basic_task(self, initialized_nuts):
                    assert initialized_nuts.general_result()["R1"].result == "R1"
            """
        )
        arguments = {
            "test_class_loading": """
                        ---
                        - test_module: basic_task
                          test_class: TestBasicTask
                          test_data: ['test1', 'test2']
                        """,
        }
        testdir.makefile(YAML_EXTENSION, **arguments)
        result = testdir.runpytest("test_class_loading.yaml")
        result.assert_outcomes(failed=1)

    def test_executes_specified_task(self, testdir):
        testdir.makepyfile(
            basic_task="""
    from pytest_nuts.context import NornirNutsContext


    class CustomNornirNutsContext(NornirNutsContext):
        def nuts_task(self):
            return lambda task: task.host.name


    CONTEXT = CustomNornirNutsContext


    class TestBasicTask:
        def test_basic_task(self, initialized_nuts):
            assert initialized_nuts.general_result()["R1"].result == "R1"
    """
        )
        arguments = {
            "test_class_loading": """
                ---
                - test_module: basic_task
                  test_class: TestBasicTask
                  test_data: ['test1', 'test2']
                """
        }
        testdir.makefile(YAML_EXTENSION, **arguments)
        result = testdir.runpytest("test_class_loading.yaml")
        result.assert_outcomes(passed=1)
