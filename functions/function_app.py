"""GM SkillsFund IQ scheduled pipeline: Azure Functions Python v2 programming model."""
import json
import logging

import azure.functions as func

from pipeline import run_once

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.function_name(name='SkillsFundScheduledReview')
@app.timer_trigger(schedule='%GM_IQ_SCHEDULE%', arg_name='timer',
                   run_on_startup=False, use_monitor=True)
def scheduled_review(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logging.warning('SkillsFund scheduled review started later than expected')
    result = run_once()
    logging.info('SkillsFund scheduled review completed: %s', result['status'])


@app.function_name(name='SkillsFundRunNow')
@app.route(route='run-now', methods=['POST'], auth_level=func.AuthLevel.FUNCTION)
def run_now(req: func.HttpRequest) -> func.HttpResponse:
    try:
        result = run_once()
    except Exception:
        logging.exception('Manual SkillsFund pipeline invocation failed')
        return func.HttpResponse(json.dumps({'status': 'FAILED', 'message': 'See function logs and Blob run status'}),
                                 status_code=500, mimetype='application/json')
    return func.HttpResponse(json.dumps(result, default=str), status_code=200,
                             mimetype='application/json')
