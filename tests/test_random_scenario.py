import pytest
from .scenario.scenario_generator import ScenarioGenerator
from .scenario.account_mgr import AccountMgr
import os

@pytest.mark.parametrize("start_round,stop_round,candidate_count,delegator_count", [
    [7,17,6,5],
    [10,50,21,15]
])
def test_random_scenario(
    start_round,
    stop_round,
    candidate_count,
    delegator_count):

    AccountMgr.init_account_mgr()
    generator = ScenarioGenerator()
    scenario = generator.generate(start_round, stop_round, candidate_count, delegator_count)

    try:
        scenario.execute()
    except Exception as e:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        file_name = f"{start_round}_{stop_round}_{candidate_count}_{delegator_count}_error.json"
        file_path = os.path.join(base_dir, 'scenario', 'config', file_name)
        scenario.dump(file_path)

        print(f"An error occurred during execute scenario {file_name}: {e}")
        assert False

    print(f"Executed {scenario.get_task_count()} scenario tasks")
