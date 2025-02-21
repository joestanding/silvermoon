import datetime
import logging
import uuid
from mongoengine import (
    Document,
    EmbeddedDocument,
    StringField,
    DateTimeField,
    DictField,
    ListField,
    ReferenceField,
    IntField,
    UUIDField,
    BooleanField,
    EmbeddedDocumentField,
)

# --------------------------------------------------------------------------- #

logging.getLogger().setLevel(logging.DEBUG)
logging.getLogger("pymongo").setLevel(logging.WARNING)

# --------------------------------------------------------------------------- #
# Worker Definitions                                                          #
# --------------------------------------------------------------------------- #

class WorkerBase(Document):
    """
    Represents a generic worker, that is either a Collector, or an Analyser.
    Both worker types share many of the same values, and can both be acted upon
    by an analyser.
    """
    uuid = UUIDField(binary=False, default=uuid.uuid4, unique=True)
    name = StringField(max_length=255, required=True)
    description = StringField(required=False)
    config = DictField()
    metadata = DictField()

    meta = {
        'allow_inheritance': True,
        'collection': 'worker',
    }

    def get_config(self, name):
        return self.config.get(name)

    def set_config(self, name, value):
        self.config[name] = value
        self.save()

# --------------------------------------------------------------------------- #

class Collector(WorkerBase):
    """
    Represents a collection worker, that takes in data from external sources
    and saves it into the database (as CollectionData) for later processing or
    review.
    """

    @property
    def last_data(self):
        channels = DataChannel.objects(collector=self)
        last_entry = CollectionData.objects(channel__in=channels).order_by('-timestamp').first()
        return last_entry.timestamp if last_entry else None

    @property
    def entry_count(self):
        channels = DataChannel.objects(collector=self)
        return CollectionData.objects(channel__in=channels).count()

# --------------------------------------------------------------------------- #

class Analyser(WorkerBase):
    """
    Represents an analysis worker, that takes in data, processes it in some
    form, and saves the result (as an AnalysisResult).
    """

    """
    Contains information on parameters this analyser expects to be passed
    by an AnalysisTask. Allows the UI to know what attributes the user must
    provide when configuring an analysis task. For example, for a GPT analyser:
    {
        "model": "The GPT model to use, e.g. gpt4o.",
        "prompt": "The prompt to be passed to GPT. Supports Jinja2 templating "
                  "to inject attributes of the data to be processed."
    }
    """
    task_parameters = DictField()

# --------------------------------------------------------------------------- #
# Stored Data Definitions                                                     #
# --------------------------------------------------------------------------- #

class StoredData(Document):
    """
    Represents any form of stored data, such as original data collected from a
    source (CollectionData), or the result of analysis of said data
    (AnalysisResult). Both contain their core information within a 'payload'
    field, and additional information in a 'metadata' field.
    """
    uuid = UUIDField(binary=False, default=uuid.uuid4, unique=True)
    name = StringField()
    timestamp = DateTimeField(default=datetime.datetime.utcnow)
    payload = DictField()
    metadata = DictField()
    display = DictField()

    meta = {
        'allow_inheritance': True,
        'collection': 'stored_data',
    }

# --------------------------------------------------------------------------- #

class CollectionData(StoredData):
    """
    Represents original data collected from a collection source (e.g. Twitter).
    This should be unaltered data, in exactly the form it was during its
    collection. This data can be analysed by an Analyser, and its result stored
    as an AnalysisResult.
    """
    friendly_text = StringField()
    channel = ReferenceField("DataChannel", required=True)

# --------------------------------------------------------------------------- #

class AnalysisResult(StoredData):
    """
    Represents the result of analysis performed by an Analyser.
    """
    # Importance level of the result ['normal', 'high']
    importance = StringField(default='normal')
    # Whether the result is hidden on the web interface by default or not
    hidden = BooleanField(default=False)
    # Reference to the analyser that produced the result
    analyser = ReferenceField("Analyser", required=True)
    # Reference to the task that was acted upon
    task = ReferenceField("AnalysisTask", required=True)
    # Reference to the CollectionData this was generated from
    origin_data = ReferenceField("CollectionData", required=True)
    # Reference to the AnalysisResult this was generated from (optional)
    origin_analysis_result = ReferenceField('self', null=True)

# --------------------------------------------------------------------------- #
# Analysis Tasks and Triggers                                                 #
# --------------------------------------------------------------------------- #

class AnalysisTaskTrigger(EmbeddedDocument):
    """
    A single trigger that can fire an AnalysisTask. For example, a translation
    task may contain multiple triggers, with one trigger instructing the task
    to run when a new Telegram message is received and to use
    payload.message_text as the translation target, and another instructing the
    task to trigger when a new Tweet is received, but with payload.tweet_text
    as the translation target.
    """

    # The events that can fire this trigger, e.g. ['NEW_DATA']
    events = ListField(StringField())

    # Which worker we want to trigger from)
    worker = ReferenceField("WorkerBase", required=True)

    # Whether the trigger should only fire on data from data sources tagged
    # with certain topics
    topics = ListField(ReferenceField("Topic"))

    # The parameters (prompt templates, model overrides, etc.)
    # for this trigger in particular
    parameters = DictField()

# --------------------------------------------------------------------------- #

class AnalysisTask(Document):
    uuid = UUIDField(binary=False, default=uuid.uuid4, unique=True)
    name = StringField(max_length=255, required=True)
    description = StringField(max_length=500, required=False)
    # Link to the Analyser that will be tasked
    analyser = ReferenceField("Analyser", required=True)
    # Which topics this task is linked to
    topics = ListField(ReferenceField("Topic"))

    # Parameter example for GPT analyser:
    # {
    #    'model': 'gpt4o',
    #    'prompt': 'Translate the following: {{ payload.original_text }}',
    # }
    parameters = DictField()

    # A list of trigger events that may cause an individual analysis task to
    # fire.
    triggers = ListField(EmbeddedDocumentField("AnalysisTaskTrigger"))

    meta = {'collection': 'analysis_task'}

# --------------------------------------------------------------------------- #
# Data Categorisation                                                         #
# --------------------------------------------------------------------------- #

class Topic(Document):
    """
    A thematic label/category, e.g. 'ukraine-war', 'financial-news'.
    A channel or an analysis requirement can link to multiple topics.
    """
    uuid = UUIDField(binary=False, default=uuid.uuid4, unique=True)
    name = StringField(max_length=100, required=True, unique=True)
    description = StringField(max_length=500)

    meta = {'collection': 'topic'}

    @property
    def channels(self):
        return DataChannel.objects(topics=self)

# --------------------------------------------------------------------------- #

class DataChannel(Document):
    uuid = UUIDField(binary=False, default=uuid.uuid4, unique=True)
    uid = StringField(max_length=255, required=True)
    name = StringField(max_length=255, required=True)
    description = StringField(required=False)
    collector = ReferenceField("Collector", required=True)
    topics = ListField(ReferenceField("Topic"))
    metadata = DictField()

    meta = {'collection': 'data_channel'}

    @property
    def entry_count(self):
        return CollectionData.objects(channel=self).count()

    @property
    def latest_entry_time(self):
        latest_entry = CollectionData.objects(channel=self).order_by('-timestamp').first()
        return latest_entry.timestamp if latest_entry else None

# --------------------------------------------------------------------------- #
# Miscellaneous                                                               #
# --------------------------------------------------------------------------- #

class WorkerError(Document):
    uuid = UUIDField(binary=False, default=uuid.uuid4, unique=True)
    worker_name = StringField(max_length=255, required=True)
    error_summary = StringField(required=True)
    error_type = StringField(max_length=255, required=True)
    traceback = StringField(required=False)
    timestamp = DateTimeField(default=datetime.datetime.utcnow)
    metadata = DictField()
    read = BooleanField(default=False)

    meta = {'collection': 'worker_error', 'ordering': ['-timestamp']}

# --------------------------------------------------------------------------- #

