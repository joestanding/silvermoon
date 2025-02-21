/* ------------------------------------------------------------------------- */
/* Globals                                                                   */
/* ------------------------------------------------------------------------- */

let triggerIndex = 0;
let triggerModal;

/* ------------------------------------------------------------------------- */
/* On Load                                                                   */
/* ------------------------------------------------------------------------- */

document.addEventListener("DOMContentLoaded", function () {
    registerAnalyserSelectHandler();
    registerTriggerModalHandlers();
    registerDeleteTaskHandler();
    registerTriggerListActionHandler();
    registerTriggerModalButtonHandler();

    setupValidation();

    updateModalParameters();

     (async function() {
        await addTriggersFromAPI();
    })();

    triggerModal = new bootstrap.Modal(document.getElementById("newTriggerModal"));
});

/* ------------------------------------------------------------------------- */
/* Validation                                                                */
/* ------------------------------------------------------------------------- */

function setupValidation() {
    (function () {
        'use strict'
        var forms = document.querySelectorAll('.needs-validation')

        // Loop over them and prevent submission
        Array.prototype.slice.call(forms)
        .forEach(function (form) {
            form.addEventListener('submit', function (event) {
                let isValid = form.checkValidity();
                let triggerExists = document.querySelector('input[type="hidden"][name^="triggers-"]') !== null;

                if(!triggerExists) {
                    isValid = false;
                    warningModal("No Triggers Configured", "You must create at least one trigger!");
                }

                if (!isValid) {
                  event.preventDefault()
                  event.stopPropagation()
                }

                form.classList.add('was-validated')
            }, false)
        })
    })();
}

/* ------------------------------------------------------------------------- */
/* Event Handlers                                                            */
/* ------------------------------------------------------------------------- */

function registerTriggerModalButtonHandler() {
    if(getMode() != 'edit' && getMode() != 'new')
        return;

    document.getElementById("addTriggerButton").addEventListener("click", function(event) {
        openTriggerModal('new', null);
    });
}

/* ------------------------------------------------------------------------- */

function registerTriggerListActionHandler() {
    if(getMode() != 'edit' && getMode() != 'new')
        return;

    document.getElementById("trigger-list").addEventListener("click", function(event) {
        if (event.target.classList.contains("trigger-delete")) {
            let el = event.target;
            let triggerId = el.getAttribute("data-trigger-id");
            deleteTrigger(triggerId);
        }
        if (event.target.classList.contains("trigger-edit")) {
            let el = event.target;
            let triggerId = el.getAttribute("data-trigger-id");
            openTriggerModal('edit', triggerId);
        }
    });
}

/* ------------------------------------------------------------------------- */

function registerDeleteTaskHandler() {
    document.getElementById("confirm-delete").addEventListener("click", function () {
        let taskUuid = document.getElementById("existing-uuid").value;
        fetch(`/task/${taskUuid}/delete`, {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.href = "/tasks"; // Redirect to task list on success
            } else {
                alert("Error: " + data.error);
            }
        })
        .catch(error => console.error("Error deleting task:", error));
    });
}

/* ------------------------------------------------------------------------- */

function registerAnalyserSelectHandler() {
    if(getMode() != 'edit' && getMode() != 'new')
        return;

    let analyserSelect = document.getElementById("analyserSelect");

    if(!analyserSelect)
        return;

    analyserSelect.addEventListener("change", function () {
        updateModalParameters();
    });
}

/* ------------------------------------------------------------------------- */

function registerTriggerModalHandlers() {
    document.getElementById("saveTriggerButton").addEventListener("click", function() {
        let modal = new bootstrap.Modal(document.getElementById("newTriggerModal"));
        let modalMode = document.getElementById("triggerModalMode").value;
        let modalIndex = document.getElementById("triggerModalIndex");

        if(modalMode == 'new') {
            addTriggerFromModal();
        }

        if(modalMode == 'edit') {
            updateTriggerFromModal();
        }

        closeTriggerModal();
    });

    document.getElementById("closeTriggerModalX").addEventListener("click", function() {
        closeTriggerModal();
    });
}

/* ------------------------------------------------------------------------- */

async function updateModalParameters() {
    if(getMode() == 'view')
        return;

    let analyserUuid = document.getElementById("analyserSelect").value;

    if(analyserUuid == "")
        return;

    let addTriggerButton = document.getElementById("addTriggerButton");
    addTriggerButton.disabled = false;

    /* Clear all existing parameter rows, we may need less now */
    clearModalParameterRows();

    /* Retrieve the analyser's required parameters */
    let data = await getAnalyserParameters(analyserUuid);
    if (!data) {
        return;
    }

    /* Create parameter rows and pre-populate them */
    for(let key in data) {
        addModalParameterRow(key, data[key]);
    }
}

/* ------------------------------------------------------------------------- */

function addModalParameterRow(key, value) {
    let table = document.getElementById("analyser-parameters");

    let tr = document.createElement("tr");
    let td1 = document.createElement("td");
    let keyInput = document.createElement("input");
    keyInput.type = 'text'
    keyInput.classList.add("form-control", "parameter-key");
    keyInput.value = key;
    keyInput.disabled = true;
    keyInput.fontFamily = "monospace";
    let td2 = document.createElement("td");
    let valueInput = document.createElement("input");
    valueInput.type = 'text'
    valueInput.classList.add("form-control", "parameter-value");
    valueInput.value = value;

    td1.appendChild(keyInput);
    td2.appendChild(valueInput);
    tr.appendChild(td1);
    tr.appendChild(td2);
    table.appendChild(tr);
}

/* ------------------------------------------------------------------------- */

function clearModalParameterRows() {
    document.querySelectorAll("#analyser-parameters > tr").forEach(
        element => element.remove()
    );
}

/* ------------------------------------------------------------------------- */

function getMode() {
    let el = document.getElementById("mode");

    if(!el)
        return null;

    return el.value;
}

/* ------------------------------------------------------------------------- */
/* Modals                                                                    */
/* ------------------------------------------------------------------------- */

function openTriggerModal(mode, triggerId) {
    let title = document.getElementById("triggerModalTitle");
    let modalMode = document.getElementById("triggerModalMode");
    let modalIndex = document.getElementById("triggerModalIndex");

    /* Reset the value inputs */
    document.querySelectorAll("#analyser-parameters .parameter-value").forEach(el => {
        el.value = "";
    });

    if(mode == 'new') {
        title.innerHTML = "Add New Trigger";
        modalMode.value = 'new';
        modalIndex.value = "";

        /* Reset the value inputs */
        document.querySelectorAll("#analyser-parameters .parameter-value").forEach(el => {
            el.value = "";
        });
    }

    if(mode == 'edit') {
        title.innerHTML = "Edit Trigger"
        modalMode.value = 'edit';
        modalIndex.value = triggerId;

        let triggerInfo = getHiddenTrigger(triggerId);

        let workerSelect = document.getElementById("newTriggerWorkerSelect");
        workerSelect.value = triggerInfo.workerUuid;
        let eventSelect = document.getElementById("newTriggerEventSelect");
        eventSelect.value = triggerInfo.eventName;

        clearModalParameterRows();

        for (const [key, value] of Object.entries(triggerInfo['params'])) {
            addModalParameterRow(key, value);
        }
    }

    triggerModal.show();
}

/* ------------------------------------------------------------------------- */

function closeTriggerModal() {
    triggerModal.hide();
}

/* ------------------------------------------------------------------------- */
/* Trigger Functions                                                         */
/* ------------------------------------------------------------------------- */

async function addTrigger(workerUuid, eventName, params) {
    workerInfo = await getWorkerInfo(workerUuid);

    addVisibleTrigger(workerInfo['name'], eventName, params);
    addHiddenTrigger(workerUuid, eventName, params);

    triggerIndex++;
}

/* ------------------------------------------------------------------------- */

async function deleteTrigger(triggerId) {
    deleteHiddenTrigger(triggerId);
    deleteVisibleTrigger(triggerId);
}

/* ------------------------------------------------------------------------- */

async function addTriggersFromAPI() {
    if(getMode() != 'edit')
        return;

    let taskUuid = document.getElementById("existing-uuid").value;
    let taskInfo = await getAnalysisTaskInfo(taskUuid);

    taskInfo.triggers.forEach(trigger => {
        addTrigger(trigger.worker_uuid, trigger.events[0], trigger.parameters);
    });

    updateTriggerIndex();
}

/* ------------------------------------------------------------------------- */

function addTriggerFromModal() {
    let triggerWorkerElem = document.getElementById("newTriggerWorkerSelect");
    let triggerWorkerUuid = triggerWorkerElem.value;
    let triggerEventElem = document.getElementById("newTriggerEventSelect");
    let triggerEventValue = triggerEventElem.value;
    let triggerParamRows = document.querySelectorAll("#analyser-parameters > tr");

    let params = {};
    triggerParamRows.forEach(row => {
        let keyElem = row.querySelector("input.parameter-key");
        let valueElem = row.querySelector("input.parameter-value");

        params[keyElem.value] = valueElem.value;
    });

    addTrigger(triggerWorkerUuid, triggerEventValue, params);
}

/* ------------------------------------------------------------------------- */

function updateTriggerFromModal() {
    let modalIndex = document.getElementById("triggerModalIndex").value;
    deleteTrigger(modalIndex);
    addTriggerFromModal();
}

/* ------------------------------------------------------------------------- */

function updateTriggerIndex() {
    const inputs = document.querySelectorAll('input[name^="triggers-"][name$="-workerUuid"]');
    let max = -1;
    inputs.forEach(input => {
        const parts = input.name.split('-');
        const idx = parseInt(parts[1], 10);
        if (idx > max) max = idx;
    });
    triggerIndex = max + 1;
}

/* ------------------------------------------------------------------------- */
/* Hidden Form Elements                                                      */
/* ------------------------------------------------------------------------- */

function addHiddenTrigger(workerUuid, eventName, params) {
    let form = document.getElementById("taskForm");

   let workerInput = document.createElement("input");
    workerInput.type = "hidden";
    workerInput.name = `triggers-${triggerIndex}-workerUuid`;
    workerInput.value = workerUuid;
    form.appendChild(workerInput);

    let eventInput = document.createElement("input");
    eventInput.type = "hidden";
    eventInput.name = `triggers-${triggerIndex}-eventName`;
    eventInput.value = eventName;
    form.appendChild(eventInput);

    let paramIndex = 0;

    Object.entries(params).forEach(([key, value]) => {
        let paramKeyInput = document.createElement("input");
        paramKeyInput.type = "hidden";
        paramKeyInput.name = `triggers-${triggerIndex}-params-${paramIndex}-key`;
        paramKeyInput.value = key;
        form.appendChild(paramKeyInput);

        let paramValueInput = document.createElement("input");
        paramValueInput.type = "hidden";
        paramValueInput.name = `triggers-${triggerIndex}-params-${paramIndex}-value`;
        paramValueInput.value = value;
        form.appendChild(paramValueInput);

        paramIndex++;
    });
}

/* ------------------------------------------------------------------------- */

function deleteHiddenTrigger(index) {
    document.querySelectorAll(`input[name^="triggers-${index}"], input[id^="triggers-${index}"]`).forEach(el => el.remove());
}

/* ------------------------------------------------------------------------- */

function getHiddenTrigger(triggerIndex) {
    const workerUuidElem = document.querySelector(`input[name="triggers-${triggerIndex}-workerUuid"]`);
    const workerUuid = workerUuidElem.value;
    const eventNameElem = document.querySelector(`input[name="triggers-${triggerIndex}-eventName"]`);
    const eventName = eventNameElem.value;

    const params = {};
    for (let i = 0;; i++) {
        const keyElem = document.querySelector(`input[name="triggers-${triggerIndex}-params-${i}-key"]`);
        const valueElem = document.querySelector(`input[name="triggers-${triggerIndex}-params-${i}-value"]`);
        if (!keyElem || !valueElem) break;
        params[keyElem.value] = valueElem.value;
    }

    return {
        'workerUuid': workerUuid,
        'eventName': eventName,
        'params': params
    };
}

/* ------------------------------------------------------------------------- */
/* Visible Trigger Table                                                     */
/* ------------------------------------------------------------------------- */

/* Pulls information from the 'New Trigger' modal and adds it to the form */
function addVisibleTrigger(workerName, eventName, params) {
    /* Adding to main trigger table */
    let table = document.getElementById("trigger-list");
    let tr = document.createElement("tr");
    tr.setAttribute("data-trigger-id", triggerIndex);

    let td1 = document.createElement("td");
    td1.innerHTML = `${workerName}`;
    tr.appendChild(td1);

    let td2 = document.createElement("td");
    td2.innerHTML = `${eventName}`;
    tr.appendChild(td2);

    let td3 = document.createElement("td");
    td3.classList.add("text-muted");
    let params_json = JSON.stringify(params);
    td3.innerHTML = `${params_json}`;
    tr.appendChild(td3);

    let td4 = document.createElement("td");
    td4.innerHTML = `<i class='fas fa-pencil trigger-edit' data-trigger-id='${triggerIndex}'></i> <i class='fas fa-trash trigger-delete' data-trigger-id='${triggerIndex}'></i>`;
    td4.style.textAlign = "right";
    tr.appendChild(td4);

    table.appendChild(tr);
}

/* ------------------------------------------------------------------------- */

function deleteVisibleTrigger(index) {
    document.querySelectorAll(`tr[data-trigger-id="${index}"]`).forEach(el => el.remove());
}

/* ------------------------------------------------------------------------- */
