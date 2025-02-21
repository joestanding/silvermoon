/* ------------------------------------------------------------------------- */
/* On Load                                                                   */
/* ------------------------------------------------------------------------- */

document.addEventListener("DOMContentLoaded", function () {
    parseAllMarkdown();
});

/* ------------------------------------------------------------------------- */

function parseAllMarkdown() {
    document.querySelectorAll(".markdown-content").forEach(el => {
        let content = el.innerHTML.trim();
        content = content.replace(/^```(?:markdown)?\n?/, "");
        content = content.replace(/\n?```$/, "");
        el.innerHTML = marked.parse(content);
    });
}

/* ------------------------------------------------------------------------- */

function warningModal(title, message) {
    const modalElement = document.getElementById('warning-modal');
    const modalTitle = modalElement.querySelector('#warningModalTitle');
    const modalBody = modalElement.querySelector('.modal-body');

    modalTitle.textContent = title;
    modalBody.textContent = message;

    const modal = new bootstrap.Modal(modalElement);
    modal.show();
}

/* ------------------------------------------------------------------------- */
/* JSON API Endpoints                                                        */
/* ------------------------------------------------------------------------- */

async function getAnalyserParameters(analyserUuid) {
    try {
        const response = await fetch(`/analyser/${analyserUuid}/json`);
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        const data = await response.json();
        console.log("Fetched task parameters:", data);

        return data['task_parameters']; // Return task parameters
    } catch (error) {
        console.error("Error fetching analyser parameters:", error);
        return null;
    }
}

/* ------------------------------------------------------------------------- */

async function getAnalysisTaskInfo(taskUuid) {
    try {
        const response = await fetch(`/task/${taskUuid}/json`);
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        const data = await response.json();
        return data
    } catch (error) {
        console.error("Error fetching task info:", error);
        return null;
    }
}

/* ------------------------------------------------------------------------- */

async function getWorkerInfo(workerUuid) {
    try {
        const response = await fetch(`/worker/${workerUuid}/json`);
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        const data = await response.json();
        return data
    } catch (error) {
        console.error("Error fetching worker info:", error);
        return null;
    }
}

/* ------------------------------------------------------------------------- */
