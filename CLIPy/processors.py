import logging
from queue import Queue
from threading import Lock
from time import sleep
from typing import Callable

from . import database as db
from .crawler import PageCrawler
from .session import Session

THREADS = 6  # high number means "Murder CLIP!", take care

log = logging.getLogger(__name__)


def task_queue_processor(session: Session, db_registry: db.SessionRegistry, task: Callable, queue: Queue):
    lock = Lock()
    threads = []
    for thread in range(0, THREADS):
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
                raise Exception("Every thread was died")
            log.info(f"Approximately {remaining_tasks} work units remaining ({alive_threads} threads alive).")
            lock.release()
            sleep(5)

    for thread in threads:
        thread.join()


def institution_task(session: Session, db_registry: db.SessionRegistry, task: Callable, restriction: int = None):
    database = db.Controller(db_registry)
    institution_queue = Queue()
    if restriction is None:
        for institution in database.get_institution_set():
            if not institution.has_time_range():  # if it has no time range to iterate through
                continue
            institution_queue.put(institution)
    else:
        institution_queue.put(database.get_institution(restriction))
    task_queue_processor(session, db_registry, task, institution_queue)


def department_task(session: Session, db_registry: db.SessionRegistry, task: Callable, inst_id: int = None):
    database = db.Controller(db_registry)
    department_queue = Queue()
    if inst_id:
        [department_queue.put(department) for department in database.get_department_set() if department.institution_id == inst_id]
    else:
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
