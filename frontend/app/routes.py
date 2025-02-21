from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_wtf import FlaskForm
from wtforms import StringField, FieldList, FormField
from mongoengine.errors import DoesNotExist
import time
import datetime
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from shared.models import (
    CollectionData, DataChannel, AnalysisTask, Collector,
    AnalysisResult, Analyser, WorkerError, Topic, WorkerBase,
    AnalysisTaskTrigger
)
from utils import paginate_query

main = Blueprint("main", __name__)

# --------------------------------------------------------------------------- #
# General Routes
# --------------------------------------------------------------------------- #

@main.route("/")
def index():
    return render_template("index.html", time=int(time.time()))


@main.route("/home")
def home():
    most_active_channels = DataChannel.objects.order_by('-latest_entry_time')[:5]
    most_active_collectors = Collector.objects.order_by('-metadata__last_data')[:5]
    return render_template(
        "home.html",
        time=int(time.time()),
        most_active_channels=most_active_channels,
        most_active_collectors=most_active_collectors
    )


@main.route("/reports")
def reports():
    return render_template("reports.html", time=int(time.time()))


@main.app_context_processor
def inject_unread_errors():
    unread_errors = WorkerError.objects(read=False).count()
    return {'unread_errors': unread_errors}

# --------------------------------------------------------------------------- #
# Data Management Routes
# --------------------------------------------------------------------------- #

@main.route("/data")
def data():
    collection_data_entries, total_records, total_pages, current_page, selected_limit = paginate_query(
        CollectionData.objects.order_by("-timestamp")
    )
    return render_template(
        "data.html",
        time=int(time.time()),
        collection_data=collection_data_entries,
        selected_limit=selected_limit,
        current_page=current_page,
        total_pages=total_pages
    )


@main.route("/data/<uuid:data_uuid>")
def data_entry_detail(data_uuid):
    data_entry = CollectionData.objects(uuid=data_uuid).first()
    if not data_entry:
        return render_template("404.html", message=f"Data entry with UUID '{data_uuid}' not found"), 404
    return render_template(
        "data_entry_detail.html",
        time=int(time.time()),
        data_entry=data_entry
    )

# --------------------------------------------------------------------------- #
# Collector Routes
# --------------------------------------------------------------------------- #

@main.route("/collectors")
def collectors():
    collectors_entries, total_records, total_pages, current_page, selected_limit = paginate_query(Collector.objects)
    return render_template(
        "collectors.html",
        time=int(time.time()),
        collectors=collectors_entries,
        selected_limit=selected_limit,
        current_page=current_page,
        total_pages=total_pages
    )


@main.route("/collector/<uuid:collector_uuid>")
def collector_detail(collector_uuid):
    collector = Collector.objects(uuid=collector_uuid).first()
    if not collector:
        return render_template("404.html", message=f"Collector with UUID '{collector_uuid}' not found"), 404
    channels = DataChannel.objects(collector=collector)
    return render_template(
        "collector_detail.html",
        time=int(time.time()),
        collector=collector,
        channels=channels
    )

# --------------------------------------------------------------------------- #
# Analyser Routes
# --------------------------------------------------------------------------- #

@main.route("/analysers")
def analysers():
    analyser_entries, total_records, total_pages, current_page, selected_limit = paginate_query(Analyser.objects)
    return render_template(
        "analysers.html",
        time=int(time.time()),
        analysers=analyser_entries,
        selected_limit=selected_limit,
        current_page=current_page,
        total_pages=total_pages
    )


@main.route("/analyser/<uuid:analyser_uuid>")
def analyser_detail(analyser_uuid):
    analyser = Analyser.objects(uuid=analyser_uuid).first()
    if not analyser:
        return render_template("404.html", message=f"Analyser with UUID '{analyser_uuid}' not found"), 404
    return render_template(
        "analyser_detail.html",
        time=int(time.time()),
        analyser=analyser
    )

# --------------------------------------------------------------------------- #
# Analysis Results Routes
# --------------------------------------------------------------------------- #

@main.route("/results")
def analysis_results():
    analysis_results_entries, total_records, total_pages, current_page, selected_limit = paginate_query(AnalysisResult.objects.order_by("-timestamp"))
    return render_template(
        "analysis_results.html",
        time=int(time.time()),
        results=analysis_results_entries,
        selected_limit=selected_limit,
        current_page=current_page,
        total_pages=total_pages
    )


@main.route("/result/<uuid:result_uuid>")
def analysis_result_detail(result_uuid):
    result = AnalysisResult.objects(uuid=result_uuid).first()
    if not result:
        return render_template("404.html", message=f"Analysis Result with UUID '{result_uuid}' not found"), 404

    try:
        task = result.task
    except DoesNotExist:
        task = None

    return render_template(
        "analysis_result_detail.html",
        time=int(time.time()),
        result=result,
        task=task,
    )

# --------------------------------------------------------------------------- #
# View Analysis Tasks                                                         #
# --------------------------------------------------------------------------- #

@main.route("/tasks")
def tasks():
    tasks_entries, total_records, total_pages, current_page, selected_limit = paginate_query(AnalysisTask.objects)
    return render_template(
        "tasks.html",
        time=int(time.time()),
        tasks=tasks_entries,
        selected_limit=selected_limit,
        current_page=current_page,
        total_pages=total_pages
    )


@main.route("/task/<uuid:task_uuid>")
def task_detail(task_uuid):
    task = AnalysisTask.objects(uuid=task_uuid).first()
    if not task:
        return render_template("404.html", message=f"Task with UUID '{task_uuid}' not found"), 404
    return render_template(
        "task_detail.html",
        time=int(time.time()),
        mode="view",
        task=task,
    )

# --------------------------------------------------------------------------- #
# Edit Analysis Tasks                                                         #
# --------------------------------------------------------------------------- #

@main.route("/task/<uuid:task_uuid>/edit", methods=["GET"])
def task_detail_edit_get(task_uuid):
    task = AnalysisTask.objects(uuid=task_uuid).first()
    analysers = Analyser.objects()
    workers = WorkerBase.objects()
    if not task:
        return render_template("404.html", message=f"Task with UUID '{task_uuid}' not found"), 404
    return render_template(
        "task_detail.html",
        time=int(time.time()),
        mode="edit",
        task=task,
        analysers=analysers,
        workers=workers
    )


@main.route("/task/<uuid:task_uuid>/edit", methods=["POST"])
def task_detail_edit_post(task_uuid):
    form = MainForm()

    analyser = Analyser.objects(uuid=form.analyser.data).first()

    triggers = []
    for trigger in form.triggers.data:
        form_worker_uuid = trigger.get('workerUuid')
        form_event_name = trigger.get('eventName')
        form_params = trigger.get('params')

        worker = WorkerBase.objects(uuid=form_worker_uuid).first()
        params = {}
        for param in form_params:
            key = param.get('key')
            value = param.get('value')
            params[key] = value

        trigger_model = AnalysisTaskTrigger(
            events=[form_event_name],
            worker=worker,
            parameters=params
        )
        triggers.append(trigger_model)

    task = AnalysisTask.objects(uuid=task_uuid).first()
    if not task:
        return render_template("404.html", message=f"Task with UUID '{task_uuid}' not found"), 404

    task.name = form.name.data
    task.description = form.description.data
    task.analyser = analyser
    task.triggers = triggers
    task.save()

    return redirect(url_for("main.task_detail", task_uuid=task.uuid))


@main.route("/task/<uuid:task_uuid>/delete", methods=["POST"])
def task_delete(task_uuid):
    task = AnalysisTask.objects(uuid=task_uuid).first()
    if not task:
        return jsonify({"error": f"Task with UUID '{task_uuid}' not found"}), 404

    task.delete()
    return jsonify({"success": True, "message": "Task deleted successfully"})

# --------------------------------------------------------------------------- #
# Create Analysis Tasks                                                       #
# --------------------------------------------------------------------------- #

class TriggerParamForm(FlaskForm):
    key = StringField('Key')
    value = StringField('Value')


class TriggerForm(FlaskForm):
    workerUuid = StringField('Worker UUID')
    eventName = StringField('Event Name')
    params = FieldList(FormField(TriggerParamForm), min_entries=1)


class MainForm(FlaskForm):
    name = StringField('Name')
    description = StringField('Description')
    analyser = StringField('Analyser')
    triggers = FieldList(FormField(TriggerForm), min_entries=1)


@main.route("/tasks/new", methods=["GET"])
def new_task_get():
    analysers = Analyser.objects()
    workers = WorkerBase.objects()
    return render_template(
        "task_detail.html",
        time=int(time.time()),
        mode="new",
        analysers=analysers,
        workers=workers
    )


@main.route("/tasks/new", methods=["POST"])
def new_task_post():
    form = MainForm()

    # Get a handle to the database entry for the analyser UUID
    analyser = Analyser.objects(uuid=form.analyser.data).first()

    # Iterate through each trigger and create an AnalysisTaskTrigger
    triggers = []
    for trigger in form.triggers.data:
        form_worker_uuid = trigger.get('workerUuid')
        form_event_name = trigger.get('eventName')
        form_params = trigger.get('params')

        worker = WorkerBase.objects(uuid=form_worker_uuid).first()
        params = {}

        for param in form_params:
            key = param.get('key')
            value = param.get('value')
            params[key] = value

        trigger_model = AnalysisTaskTrigger(
            events=[form_event_name],
            worker=worker,
            parameters=params
        )
        triggers.append(trigger_model)

    task = AnalysisTask(
        name=form.name.data,
        description=form.description.data,
        analyser=analyser,
        triggers=triggers
    ).save()

    return redirect(url_for("main.tasks"))

# --------------------------------------------------------------------------- #
# Channel Routes
# --------------------------------------------------------------------------- #

class ListQuerySet:
    """A wrapper to provide .count(), .skip(), .limit(), and iteration on a list."""
    def __init__(self, data):
        self.data = data

    def count(self):
        return len(self.data)

    def skip(self, num):
        self.data = self.data[num:]
        return self

    def limit(self, num):
        self.data = self.data[:num]
        return self

    def __iter__(self):
        return iter(self.data)


@main.route("/channels")
def channels():
    channels_entries = list(DataChannel.objects())
    channel_timestamps = {
        channel.id: CollectionData.objects(channel=channel).order_by("-timestamp").first()
        for channel in channels_entries
    }
    sorted_channels = sorted(
        channels_entries,
        key=lambda c: channel_timestamps.get(c.id).timestamp if channel_timestamps.get(c.id) else datetime.min,
        reverse=True
    )
    sorted_channels_queryset = ListQuerySet(sorted_channels)
    paginated_channels, total_records, total_pages, current_page, selected_limit = paginate_query(sorted_channels_queryset)

    if not sorted_channels:
        paginated_channels = None

    return render_template(
        "channels.html",
        time=int(time.time()),
        channels=paginated_channels,
        selected_limit=selected_limit,
        current_page=current_page,
        total_pages=total_pages
    )


@main.route("/channel/<uuid:channel_uuid>")
def channel_detail(channel_uuid):
    channel = DataChannel.objects(uuid=channel_uuid).first()
    if not channel:
        return render_template("404.html", message=f"Channel with UUID '{channel_uuid}' not found"), 404
    collection_entries = CollectionData.objects(channel=channel).order_by("-timestamp").limit(10)
    return render_template(
        "channel_detail.html",
        time=int(time.time()),
        channel=channel,
        collection_entries=collection_entries
    )


@main.route("/channel/<uuid:channel_uuid>/stats")
def channel_data_stats(channel_uuid):
    channel = DataChannel.objects(uuid=str(channel_uuid)).first()
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=29)
    date_counts = defaultdict(int)
    entries = CollectionData.objects(channel=channel, timestamp__gte=start_date).only("timestamp")
    for entry in entries:
        date_str = entry.timestamp.strftime("%Y-%m-%d")
        date_counts[date_str] += 1
    labels = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
    values = [date_counts[date] for date in labels]
    return jsonify({"labels": labels, "values": values})

# --------------------------------------------------------------------------- #
# Topics Routes
# --------------------------------------------------------------------------- #

@main.route("/topics")
def topics():
    topics_entries, total_records, total_pages, current_page, selected_limit = paginate_query(Topic.objects)
    return render_template(
        "topics.html",
        time=int(time.time()),
        topics=topics_entries,
        selected_limit=selected_limit,
        current_page=current_page,
        total_pages=total_pages
    )


@main.route("/topic/<uuid:topic_uuid>")
def topic_detail(topic_uuid):
    topic = Topic.objects(uuid=topic_uuid).first()
    if not topic:
        return render_template("404.html", message=f"Topic with UUID '{topic_uuid}' not found"), 404
    return render_template(
        "topic_detail.html",
        time=int(time.time()),
        topic=topic
    )

# --------------------------------------------------------------------------- #
# Error Handling Routes
# --------------------------------------------------------------------------- #

@main.route("/errors")
def errors():
    errors_entries, total_records, total_pages, current_page, selected_limit = paginate_query(
        WorkerError.objects.order_by("-timestamp")
    )
    return render_template(
        "errors.html",
        time=int(time.time()),
        errors=errors_entries,
        selected_limit=selected_limit,
        current_page=current_page,
        total_pages=total_pages
    )


@main.route("/error/<uuid:error_uuid>")
def error_detail(error_uuid):
    error = WorkerError.objects(uuid=error_uuid).first()
    error.read = True
    error.save()
    if not error:
        return render_template("404.html", message=f"Error entry with UUID '{error_uuid}' not found"), 404
    return render_template(
        "error_detail.html",
        time=int(time.time()),
        error=error
    )

# --------------------------------------------------------------------------- #
# JSON Endpoints                                                              #
# --------------------------------------------------------------------------- #

@main.route("/workers/json")
def workers_json():
    workers = WorkerBase.objects()
    print(workers.to_json())
    return jsonify(json.loads(workers.to_json()))


@main.route("/worker/<uuid:worker_uuid>/json")
def worker_json(worker_uuid):
    worker = WorkerBase.objects(uuid=worker_uuid).first()
    if not worker:
        return render_template("404.html", message=f"Worker with UUID '{worker_uuid}' not found"), 404
    return jsonify(json.loads(worker.to_json()))


@main.route("/analysers/json")
def analysers_json():
    analysers = Analyser.objects()
    print(analysers.to_json())
    return jsonify(json.loads(analysers.to_json()))


@main.route("/analyser/<uuid:analyser_uuid>/json")
def analyser_json(analyser_uuid):
    analyser = Analyser.objects(uuid=analyser_uuid).first()
    if not analyser:
        return render_template("404.html", message=f"Analyser with UUID '{analyser_uuid}' not found"), 404
    return jsonify(json.loads(analyser.to_json()))


@main.route("/collectors/json")
def collectors_json():
    collectors = Collector.objects()
    return jsonify(collectors)


@main.route("/collector/<uuid:collector_uuid>/json")
def collector_json(collector_uuid):
    collector = Analyser.objects(uuid=collector_uuid).first()
    if not collector:
        return render_template("404.html", message=f"Analyser with UUID '{collector_uuid}' not found"), 404
    return jsonify(json.loads(collector.to_json()))


@main.route("/tasks/json")
def tasks_json():
    tasks = Tasks.objects()
    return jsonify(tasks)


@main.route("/task/<uuid:task_uuid>/json")
def task_json(task_uuid):
    task = AnalysisTask.objects(uuid=task_uuid).first()
    if not task:
        return render_template("404.html", message=f"Task with UUID '{task_uuid}' not found"), 404

    # Dirty hack until I bin off UUIDs and replace them with native IDs
    task_dict = json.loads(task.to_json())
    for index, trigger in enumerate(task_dict['triggers']):
        task_dict['triggers'][index]['worker_uuid'] = task.triggers[index].worker.uuid;

    return jsonify(task_dict)
