from app.core.celery_app import celery_app


def enqueue(task_name: str, *args: object) -> bool:
    try:
        celery_app.send_task(task_name, args=list(args))
        return True
    except Exception:
        return False
