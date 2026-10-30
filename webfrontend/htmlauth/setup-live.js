/* Refresh device cards without navigating, losing drafts or replaying actions. */
(function () {
    'use strict';
    var banner = document.getElementById('sl-live-status');
    if (!banner || !window.fetch || !window.DOMParser) return;
    var fetching = false, sending = false, generation = 0, dirty = new Set();
    async function request(url, options) {
        var controller = new AbortController();
        var timer = setTimeout(function () { controller.abort(); }, 15000);
        try { return await fetch(url, Object.assign({}, options, {signal: controller.signal})); }
        finally { clearTimeout(timer); }
    }
    var endpoint = new URL('index.php', window.location.href);
    document.addEventListener('click', async function (event) {
        var exportLink = event.target.closest('a[href="#loxone-export"]');
        if (exportLink) document.getElementById('loxone-export').open = true;
        var button = event.target.closest('[data-copy-text]');
        if (!button) return;
        var panel = button.closest('[data-copied]');
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(button.dataset.copyText);
            } else {
                var area = document.createElement('textarea');
                area.value = button.dataset.copyText;
                area.style.position = 'fixed'; area.style.left = '-9999px';
                document.body.appendChild(area); area.select();
                try { if (!document.execCommand('copy')) throw new Error('copy'); }
                finally { area.remove(); }
            }
            banner.textContent = panel.dataset.copied;
        } catch (_) { banner.textContent = panel.dataset.copyFailed; }
        button.blur();
    });
    document.addEventListener('input', function (event) {
        var card = event.target.closest('[data-device]');
        if (card) dirty.add(card.dataset.device);
    });
    document.addEventListener('change', function (event) {
        var card = event.target.closest('[data-device]');
        if (card) dirty.add(card.dataset.device);
    });
    async function refresh() {
        if (fetching || sending || document.hidden) return;
        fetching = true;
        var started = generation;
        try {
            var response = await request(endpoint, {credentials: 'same-origin', cache: 'no-store'});
            if (!response.ok) throw new Error('status');
            var doc = new DOMParser().parseFromString(await response.text(), 'text/html');
            var section = document.getElementById('sl-devices');
            if (!doc.getElementById('sl-devices')) throw new Error('session');
            if (sending || generation !== started) return;
            doc.querySelectorAll('[data-device]').forEach(function (next) {
                var old = Array.from(section.querySelectorAll('[data-device]')).find(function (item) {
                    return item.dataset.device === next.dataset.device;
                });
                if (dirty.has(next.dataset.device) || (old && old.contains(document.activeElement) && /^(INPUT|SELECT|TEXTAREA|BUTTON)$/.test(document.activeElement.tagName))) return;
                if (old) {
                    // Match by summary text: conditional setup details can change order.
                    var opened = Array.from(old.querySelectorAll('details[open]')).map(function (d) {
                        return d.querySelector('summary').textContent;
                    });
                    next.querySelectorAll('details').forEach(function (d) {
                        d.open = opened.includes(d.querySelector('summary').textContent);
                    });
                    old.replaceWith(next);
                } else section.appendChild(next);
            });
            var summary = document.querySelector('.sl-status');
            var nextSummary = doc.querySelector('.sl-status');
            if (summary && nextSummary) summary.replaceWith(nextSummary);
            var progress = document.getElementById('sl-discovery-progress');
            var nextProgress = doc.getElementById('sl-discovery-progress');
            if (progress && nextProgress) progress.replaceWith(nextProgress);
            if (banner.textContent === banner.dataset.error) banner.textContent = banner.dataset.ok;
            if (typeof wireReports === 'function') wireReports();
        } catch (_) {
            banner.textContent = banner.dataset.error;
        } finally { fetching = false; }
    }
    document.addEventListener('submit', async function (event) {
        var form = event.target;
        if (form.method.toLowerCase() !== 'post' || !form.closest('main')) return;
        event.preventDefault();
        if (sending) return;
        sending = true;
        generation += 1;
        var data = new FormData(form);
        var buttons = Array.from(form.querySelectorAll('button'));
        buttons.forEach(function (b) { b.disabled = true; });
        try {
            var response = await request(endpoint, {method: 'POST', body: data,
                credentials: 'same-origin', headers: {'Accept': 'application/json'}});
            if (!response.ok) throw new Error('request');
            var result = await response.json();
            banner.textContent = result.message;
            // Put feedback beside the action as well as in the live region.
            var notice = form.querySelector('.sl-action-result');
            if (!notice) {
                notice = document.createElement('p');
                notice.className = 'sl-action-result'; notice.setAttribute('role', 'status');
                form.appendChild(notice);
            }
            notice.textContent = result.message;
            if (result.ok) {
                var card = form.closest('[data-device]');
                if (card) dirty.delete(card.dataset.device);
                if (data.get('action') === 'language') window.location.reload();
            }
        } catch (_) {
            // A timed-out POST may have been accepted. Never retry it automatically.
            banner.textContent = banner.dataset.unsent;
        } finally {
            sending = false;
            buttons.forEach(function (b) { b.disabled = false; });
            // Release button focus so new state can replace this card.
            if (buttons.includes(document.activeElement)) document.activeElement.blur();
            setTimeout(refresh, 2500);
        }
    });
    setInterval(refresh, 5000);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) refresh(); });
}());
