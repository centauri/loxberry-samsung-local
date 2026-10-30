// Run with NODE_PATH pointing to a development-only jsdom installation.
const {JSDOM} = require('jsdom');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const fixture = (label) => `<main><section id="sl-devices"><article data-device="tv">
<p class="value">${label}</p><details><summary>Details</summary></details>
<form method="post"><input name="csrf" value="test-csrf" type="hidden">
<input name="action" value="device" type="hidden"><input type="checkbox" name="control">
<button type="submit">Save</button></form></article></section>
<p id="sl-live-status" data-error="error" data-ok="ok" data-unsent="unknown">ok</p></main>`;
const dom = new JSDOM(fixture('old'), {url:'http://localhost/index.php', runScripts:'outside-only', pretendToBeVisual:true});
const w = dom.window;
let poll, response = 'new', posts = 0, rejectPost = false;
w.setInterval = (fn) => { poll = fn; };
const originalTimeout = w.setTimeout.bind(w);
w.setTimeout = (fn, ms) => ms === 2500 ? 0 : originalTimeout(fn, ms);
w.fetch = async (_url, options) => {
    if (options.method === 'POST') {
        posts++;
        assert.equal(options.body.get('csrf'), 'test-csrf');
        if (rejectPost) throw Error('connection lost after possible acceptance');
        return {ok:true, json:async()=>({ok:true,message:'saved'})};
    }
    return {ok:true, text:async()=>fixture(response)};
};
w.eval(fs.readFileSync('webfrontend/htmlauth/setup-live.js','utf8'));
const settle = () => new Promise(resolve => setImmediate(resolve));
(async () => {
    w.document.querySelector('details').open = true;
    await poll();
    assert.equal(w.document.querySelector('.value').textContent, 'new');
    assert.equal(w.document.querySelector('details').open, true);
    let control = w.document.querySelector('[name=control]');
    control.checked = true;
    control.dispatchEvent(new w.Event('change', {bubbles:true}));
    response = 'paired';
    await poll();
    assert.equal(w.document.querySelector('.value').textContent, 'new');
    assert.equal(control.checked, true); // unsaved draft survived polling
    w.document.querySelector('form').dispatchEvent(new w.Event('submit', {bubbles:true,cancelable:true}));
    await settle();
    assert.equal(posts, 1);
    await poll();
    assert.equal(w.document.querySelector('.value').textContent, 'paired');
    rejectPost = true;
    w.document.querySelector('form').dispatchEvent(new w.Event('submit', {bubbles:true,cancelable:true}));
    await settle();
    assert.equal(w.document.querySelector('#sl-live-status').textContent, 'unknown');
    await poll(); await poll();
    assert.equal(posts, 2); // failed write was never replayed
    const panel = w.document.createElement('div');
    panel.dataset.copied = 'copied'; panel.dataset.copyFailed = 'copy failed';
    panel.innerHTML = '<button type="button" data-copy-text="samsunglocal/test/remote/available">Copy</button>';
    w.document.body.appendChild(panel);
    w.document.execCommand = (command) => {
        assert.equal(command, 'copy');
        assert.equal(w.document.querySelector('textarea').value, 'samsunglocal/test/remote/available');
        return true;
    };
    panel.querySelector('button').click(); await settle();
    assert.equal(w.document.querySelector('#sl-live-status').textContent, 'copied');
    assert.equal(w.document.querySelector('textarea'), null);
    w.document.execCommand = () => false;
    panel.querySelector('button').click(); await settle();
    assert.equal(w.document.querySelector('#sl-live-status').textContent, 'copy failed');
    dom.window.close();
    console.log('Live UI: polling, open details, unsaved edits, async save and no write replay passed');
})().catch(error => { console.error(error); dom.window.close(); process.exitCode=1; });
