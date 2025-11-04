from app.query.registry import QueryModelRegistry


def test_query_registry_smoke_default():
    reg = QueryModelRegistry()
    model = reg.get('default')
    out = model.answer({ 'query': 'What is the A1c?' })
    assert isinstance(out, dict)
    assert out.get('model_id') == 'default'
    assert 'answer' in out
