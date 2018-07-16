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
        lock.acquire()
        if queue.empty():
            lock.release()
            break
        else:
            log.info("Approximately {} work units remaining".format(queue.qsize()))
            lock.release()
            sleep(5)

    for thread in threads:
        thread.join()


def institution_task(session: Session, db_registry: db.SessionRegistry, task: Callable):
    database = db.Controller(db_registry)
    institution_queue = Queue()
    for institution in database.get_institution_set():
        if not institution.has_time_range():  # if it has no time range to iterate through
            continue
        institution_queue.put(institution)
    task_queue_processor(session, db_registry, task, institution_queue)


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
