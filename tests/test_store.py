from app.store import JobStore


def test_recovery_and_persistence(tmp_path):
    path = str(tmp_path / 'jobs.sqlite3')
    db = JobStore(path)
    db.initialize()
    job = db.add_many(['https://example.org/one'])[0]
    active = db.next_job()
    assert active['id'] == job['id']
    db.initialize()
    assert db.get(job['id'])['status'] == 'queued'
    db.update(job['id'], 'manual', note='Captcha')
    assert db.get(job['id'])['note'] == 'Captcha'
    assert db.reset(job['id'])
    assert db.get(job['id'])['status'] == 'queued'
