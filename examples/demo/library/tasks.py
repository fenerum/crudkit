import time

from celery import shared_task

from crudkit import jobs


@shared_task
def fetch_reviews(job_id):
    with jobs.resume(job_id):
        sources = ["Library journal", "Book club", "Newspaper", "Blog"]
        for done, source in enumerate(sources, 1):
            time.sleep(0.5)
            jobs.progress(done, total=len(sources), message=source)
