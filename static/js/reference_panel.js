(() => {
    const launcher = document.querySelector("[data-reference-open]");
    const panel = document.querySelector("[data-reference-panel]");
    const closeButton = document.querySelector("[data-reference-close]");
    const dragHandle = document.querySelector("[data-reference-drag]");

    if (!launcher || !panel || !closeButton || !dragHandle) {
        return;
    }

    let dragState = null;

    function clamp(value, min, max) {
        return Math.min(Math.max(value, min), max);
    }

    function panelBounds(left, top) {
        const rect = panel.getBoundingClientRect();
        const margin = 12;
        return {
            left: clamp(left, margin, window.innerWidth - rect.width - margin),
            top: clamp(top, margin, window.innerHeight - rect.height - margin),
        };
    }

    function movePanel(left, top) {
        const next = panelBounds(left, top);
        panel.style.left = `${next.left}px`;
        panel.style.top = `${next.top}px`;
    }

    function openPanel() {
        panel.hidden = false;
        launcher.setAttribute("aria-expanded", "true");

        const rect = panel.getBoundingClientRect();
        if (!panel.style.left || !panel.style.top) {
            movePanel(rect.left, rect.top);
        } else {
            movePanel(rect.left, rect.top);
        }
    }

    function closePanel() {
        panel.hidden = true;
        launcher.setAttribute("aria-expanded", "false");
        launcher.focus();
    }

    launcher.addEventListener("click", () => {
        if (panel.hidden) {
            openPanel();
        } else {
            closePanel();
        }
    });

    closeButton.addEventListener("click", closePanel);

    dragHandle.addEventListener("pointerdown", (event) => {
        if (event.target.closest("button")) {
            return;
        }

        const rect = panel.getBoundingClientRect();
        dragState = {
            pointerId: event.pointerId,
            offsetX: event.clientX - rect.left,
            offsetY: event.clientY - rect.top,
        };
        dragHandle.setPointerCapture(event.pointerId);
    });

    dragHandle.addEventListener("pointermove", (event) => {
        if (!dragState || event.pointerId !== dragState.pointerId) {
            return;
        }

        movePanel(event.clientX - dragState.offsetX, event.clientY - dragState.offsetY);
    });

    function stopDragging(event) {
        if (!dragState || event.pointerId !== dragState.pointerId) {
            return;
        }

        dragState = null;
    }

    dragHandle.addEventListener("pointerup", stopDragging);
    dragHandle.addEventListener("pointercancel", stopDragging);

    window.addEventListener("resize", () => {
        if (panel.hidden) {
            return;
        }

        const rect = panel.getBoundingClientRect();
        movePanel(rect.left, rect.top);
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !panel.hidden) {
            closePanel();
        }
    });
})();
