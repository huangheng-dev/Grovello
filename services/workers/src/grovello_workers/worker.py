import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from grovello_workers.activities.growth import execute_growth_action, prepare_growth_decision
from grovello_workers.settings import get_settings
from grovello_workers.workflows.growth_loop import GrowthLoopWorkflow


async def run_worker() -> None:
    settings = get_settings()
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[GrowthLoopWorkflow],
        activities=[prepare_growth_decision, execute_growth_action],
    )
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
