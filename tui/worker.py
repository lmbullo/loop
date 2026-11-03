import threading

from . import client


class Worker(threading.Thread):
    def __init__(self, model, interval=0.5):
        super().__init__(daemon=True)
        self.model = model
        self.interval = interval
        self.stop_event = threading.Event()

    def stop(self):
        self.stop_event.set()

    def enqueue(self, text):
        try:
            created, reply = client.enqueue(text)
        except Exception as e:
            self.model.say(f"enqueue {type(e).__name__}: {e}")
            return None
        item = (reply or {}).get("item") or {}
        self.model.say(f"queued {item.get('id')}" + (" (daemon started)" if created else ""))
        return item

    def drop(self, item_id):
        try:
            client.drop(item_id)
        except Exception as e:
            self.model.say(f"drop {type(e).__name__}: {e}")
            return None
        self.model.say(f"dropped {item_id}")
        return True

    def move(self, item_id, delta):
        try:
            client.move(item_id, delta)
        except Exception as e:
            self.model.say(f"move {type(e).__name__}: {e}")
            return None
        return True

    def run(self):
        try:
            client.ensure()
        except Exception as e:
            self.model.set_down(f"start {type(e).__name__}: {e}")
        while not self.stop_event.is_set():
            try:
                self.model.apply(client.snapshot())
            except Exception as e:
                self.model.set_down(f"{type(e).__name__}: {e}")
            self.stop_event.wait(self.interval)
