from mongoengine import connect
from shared.models import (
    Collector,
    DataChannel,
    CollectionData,
    WorkerError,
    AnalysisResult,
    Analyser,
    AnalysisTask,
    WorkerBase
)
import traceback
import logging
import sys
import pprint
import json
import redis

logging.getLogger().setLevel(logging.DEBUG)

EVENT_NEW_DATA     = "NEW_DATA"
EVENT_NEW_ANALYSIS = "NEW_ANALYSIS_RESULT"

# --------------------------------------------------------------------------- #

connect(db="silvermoon", host="database")

# --------------------------------------------------------------------------- #
# Custom Worker Exceptions                                                    #
# --------------------------------------------------------------------------- #

class ConfigMissingException(Exception):
    def __init__(self):
        super().__init__()

# --------------------------------------------------------------------------- #
# Event Queue                                                                 #
# --------------------------------------------------------------------------- #

class Event:
    def __init__(self, name, data):
        self.name = name
        self.data = data
        self.worker = self._get_worker_from_uuid(data['worker_uuid'])


    def _get_worker_from_uuid(self, uuid):
        x = WorkerBase.objects(uuid=str(uuid),
           __raw__={"_cls":{"$in": ["WorkerBase.Collector", "WorkerBase.Analyser"]}}
        ).first()

        return x


    def is_new_data(self):
        if self.name == EVENT_NEW_DATA:
            return True
        else:
            return False

# --------------------------------------------------------------------------- #

class NewDataEvent(Event):
    def __init__(self, name, data):
        super().__init__(name, data)


    def get_db_record(self):
        return CollectionData.objects(uuid=self.data['record_uuid']).first()

# --------------------------------------------------------------------------- #

class NewResultEvent(Event):
    def __init__(self, name, data):
        super().__init__(name, data)


    def get_db_record(self):
        return AnalysisResult.objects(uuid=self.data['record_uuid']).first()

# --------------------------------------------------------------------------- #
# Worker Base Class                                                           #
# --------------------------------------------------------------------------- #

class Worker:
    def __init__(self, name):
        self.name = name
        self.db_entry = None
        self.redis = redis.Redis(host='redis', port=6379, db=0)
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe(EVENT_NEW_DATA, EVENT_NEW_ANALYSIS)


    def safe_str(self, obj):
        try:
            return pprint.pformat(obj)
        except Exception:
            return repr(obj)


    def start(self):
        raise NotImplementedError("Subclasses must implement this method")


    def get_config(self, name):
        return self.db_entry.get_config(name)


    def set_config(self, name, value):
        return self.db_entry.set_config(name, value)


    def register_config(self, name, default_value):
        if name not in self.db_entry.config:
            self.db_entry.config[name] = default_value;
            self.db_entry.save()


    def on_error(self, metadata=None):
        logging.error("ERROR!!!")

        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback_str = "".join(traceback.format_exception(exc_type,
                                                           exc_value,
                                                           exc_traceback))

        error_summary = str(exc_value) if exc_value else "Unknown error"
        error_type = exc_type.__name__ if exc_type else "UnknownException"
        
        logging.debug(traceback_str)

        WorkerError(
            worker_name=self.name,
            error_summary=error_summary,
            error_type=error_type,
            traceback=traceback_str,
            metadata=metadata
        ).save() 


    def raise_event(self, event_name, data=None):
        data = data or {}
        data['worker_uuid'] = str(self.db_entry.uuid)
        self.redis.publish(event_name, json.dumps(data))


    def listen_for_events(self):
        for message in self.pubsub.listen():
            if message['type'] != 'message':
                continue

            event_name = message['channel'].decode('ascii')

            if event_name == EVENT_NEW_DATA:
                yield NewDataEvent(event_name, json.loads(message['data']))
            elif event_name == EVENT_NEW_ANALYSIS:
                yield NewResultEvent(event_name, json.loads(message['data']))
            else:
                yield Event(event_name, json.loads(message['data']))


    def get_channel(self, uid):
        return DataChannel.objects(uid=uid).first()


    def add_channel(self, name, uid, description=None, metadata=None):
        existing_channel = DataChannel.objects(collector=self.db_entry,
                                               uid=uid).first()
        if existing_channel:
            return existing_channel

        return DataChannel(
            name=name,
            uid=str(uid),
            description=description,
            metadata=metadata,
            collector=self.db_entry
        ).save()

# --------------------------------------------------------------------------- #
# Collector Worker                                                            #
# --------------------------------------------------------------------------- #

class CollectorWorker(Worker):
    def __init__(self, name):
        super().__init__(name)
        self.db_entry = self._register_collector()


    def _register_collector(self):
        existing = Collector.objects(name=self.name).first()
        if existing:
            return existing
        return Collector(name=self.name).save()


    def add_data(self, channel_uid, payload, friendly_text=None):
        channel = self.get_channel(str(channel_uid))

        if channel is None:
            logging.error(f"get_channel() returned None for UID {channel_uid}")
            return None

        data = CollectionData(
            channel=channel,
            payload=payload,
            friendly_text=friendly_text
        ).save()

        self.raise_event(EVENT_NEW_DATA, { 'record_uuid': str(data.uuid) })

# --------------------------------------------------------------------------- #
# Analyser Worker                                                             #
# --------------------------------------------------------------------------- #

class AnalyserWorker(Worker):
    def __init__(self, name):
        super().__init__(name)
        self.db_entry = self._register_analyser()


    def _register_analyser(self):
        existing = Analyser.objects(name=self.name).first()
        if existing:
            return existing
        return Analyser(name=self.name).save()


    def _get_tasks(self, event):
        """
        Return all AnalysisTasks that should fire from the given event.
        """
        logging.debug(f"Getting tasks for event: {event}")
        tasks = AnalysisTask.objects(
            analyser=self.db_entry,
            triggers__events__in=[event.name] # Looks in ['triggers']['events']
        )
        logging.debug(f"Returned tasks: {tasks}, refining..")

        for task in tasks:
            logging.debug(f"Checking task '{task}'")
            for trigger in task.triggers:
                logging.debug(f"Checking trigger '{trigger}'")
                logging.debug(f"trigger.events:     {trigger.events}")
                logging.debug(f"trigger.worker:     {trigger.worker}")
                logging.debug(f"trigger.parameters: {trigger.parameters}")
                logging.debug(f"event.worker:       {event.worker}")
                if trigger.worker.uuid == event.worker.uuid:
                    logging.debug("Trigger worker UUID matches event UUID")
                    yield task, trigger


    def register_parameter(self, key, value):
        self.db_entry.task_parameters[key] = value


    def listen_for_tasks(self):
        """
        Read events from the Redis queue and return AnalysisTasks that should
        fire upon them.
        """
        for event in self.listen_for_events():
            record = event.get_db_record()
            for task, trigger in self._get_tasks(event):
                yield record, task, trigger


    def save_result(self, name, payload, record, task, **kwargs):
        logging.info(f"Saving analysis result: '{name}'")
        logging.debug(f"Payload: {payload}")

        # TODO: Add support for saving result generated from another result

        AnalysisResult(
            name=name,
            hidden=False,
            analyser=self.db_entry,
            payload=payload,
            origin_data=record,
            task=task,
            **kwargs
        ).save()

# --------------------------------------------------------------------------- #
