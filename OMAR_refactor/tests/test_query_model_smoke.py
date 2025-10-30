from app.query.query_models.default.provider import model


def test_model_smoke_no_patient():
    out = model.answer({ 'prompt': 'What is the A1c?' })
    assert isinstance(out, dict)
    assert out.get('model_id') == 'default'
    assert 'answer' in out
