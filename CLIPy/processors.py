import logging
from queue import Queue
from threading import Lock
from time import sleep
from typing import Callable

from . import database as db
from .config import CLIPY_THREADS
from .crawler import PageCrawler
from .session import Session

log = logging.getLogger(__name__)


def task_queue_processor(session: Session, db_registry: db.SessionRegistry, task: Callable, queue: Queue):
    lock = Lock()
    threads = []
    for thread in range(0, CLIPY_THREADS):
        threads.append(PageCrawler("Thread-" + str(thread), session, db_registry, queue, lock, task))
        threads[thread].start()

    while True:
        alive_threads = 0
        for thread in threads:
            if thread.is_alive():
                alive_threads += 1
        lock.acquire()
        remaining_tasks = queue.qsize()
        if remaining_tasks == 0:
            lock.release()
            break
        else:
            if alive_threads == 0:
                raise Exception("Every thread has died")
            log.info(f"Approximately {remaining_tasks} work units remaining ({alive_threads} threads alive).")
            lock.release()
            sleep(10)

    for thread in threads:
        thread.join()


def year_task(session: Session, db_registry: db.SessionRegistry, task: Callable, from_year, to_year):
    year_queue = Queue()
    [year_queue.put(year) for year in range(from_year, to_year+1)]
    task_queue_processor(session, db_registry, task, year_queue)

def building_task(session: Session, db_registry: db.SessionRegistry, task: Callable):
    database = db.Controller(db_registry)
    department_queue = Queue()
    [department_queue.put(department) for department in database.get_building_set()]
    task_queue_processor(session, db_registry, task, department_queue)


def department_task(session: Session, db_registry: db.SessionRegistry, task: Callable):
    database = db.Controller(db_registry)
    department_queue = Queue()
    [department_queue.put(department) for department in database.get_department_set()]
    task_queue_processor(session, db_registry, task, department_queue)


def class_task(session: Session, db_registry: db.SessionRegistry, task: Callable, year=None, period=None):
    database = db.Controller(db_registry)
    class_instance_queue = Queue()
    if year is None:
        class_instances = database.fetch_class_instances()
    else:
        if period is None:
            class_instances = database.fetch_class_instances(year=year)
        else:
            class_instances = database.fetch_class_instances(year=year, period=period)
    [class_instance_queue.put(class_instance) for class_instance in class_instances]
    task_queue_processor(session, db_registry, task, class_instance_queue)
