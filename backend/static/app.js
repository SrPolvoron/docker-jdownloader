const $ = (id) => document.getElementById(id);
const headers = {'Content-Type': 'application/json', 'X-JFStack-Request': '1'};
async function call(path, method='GET', data=null) {
  const res = await fetch(path, {method, headers: method === 'GET' ? undefined : headers,
    body: data ? JSON.stringify(data) : method === 'GET' ? undefined : '{}',
    cache: 'no-store', credentials: 'same-origin'});
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
  return body;
}
function notify(message, bad=false) {
  const el = $('notification'); el.textContent = message;
  el.className = bad ? 'bad' : 'good';
}
function create(tag, className='', text='') {
  const el = document.createElement(tag); el.className = className; el.textContent = text; return el;
}
function render(jobs) {
  const target = $('job-list'); target.replaceChildren();
  if (!jobs.length) {target.append(create('p', 'empty', 'No jobs yet.')); return;}
  jobs.forEach(job => {
    const article = create('article', 'job');
    const top = create('div','job-top');
    top.append(create('span', 'pill ' + job.status, job.status.toUpperCase()));
    const time = create('time','date', new Date(job.created_at * 1000).toLocaleString()); top.append(time);
    const url = create('div','url',job.original_url); url.title=job.original_url;
    article.append(top,url);
    if (job.final_url && job.final_url !== job.original_url) {
      const finalUrl = create('div','final-url','→ ' + job.final_url); finalUrl.title=job.final_url; article.append(finalUrl);
    }
    if (job.note) article.append(create('p','note',job.note));
    if (['manual','ready','error'].includes(job.status)) {
      const bar = create('div','job-actions');
      const retry = create('button','tiny','Retry resolution');
      retry.addEventListener('click', async () => {
        retry.disabled=true;
        try {await call(`/api/jobs/${job.id}/retry`,'POST'); await refresh();}
        catch(e) {notify(e.message,true);} finally {retry.disabled=false;}
      });
      const send = create('button','tiny secondary','Send URL to JDownloader');
      send.addEventListener('click', async () => {
        send.disabled=true;
        try {await call(`/api/jobs/${job.id}/send`,'POST'); await refresh();}
        catch(e) {notify(e.message,true);} finally {send.disabled=false;}
      });
      bar.append(retry,send); article.append(bar);
    }
    target.append(article);
  });
}
async function refresh() {
  try {
    const [jobs,status] = await Promise.all([call('/api/jobs'),call('/api/status')]);
    render(jobs.jobs); $('max-batch').textContent=status.max_batch;
    const state = $('jd-state'); const ready=status.jdownloader_cnl_ready;
    state.replaceChildren(create('span','dot'), document.createTextNode(ready ? 'JDownloader connected' : 'JDownloader not ready'));
    state.className='status ' + (ready ? 'online' : 'offline');
  } catch(e) {notify(e.message,true);}
}
$('add-btn').addEventListener('click', async () => {
  const btn = $('add-btn'); btn.disabled=true;
  try {
    const response=await call('/api/jobs','POST',{links:$('links').value});
    $('links').value=''; notify(`Queued ${response.jobs.length} link(s) for resolution.`);
    await refresh();
  } catch(e) {notify(e.message,true);} finally {btn.disabled=false;}
});
$('refresh-btn').addEventListener('click', refresh);
refresh(); setInterval(refresh, 6000);
