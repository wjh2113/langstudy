from app.note_quality import clean_notes


def test_cleanup_preserves_specific_usage_and_translations():
    data = {'patterns': [
        {'pattern': 'Please let me know.', 'usage': '在“安排出差”情境中，根据具体语境完成表达与回应。',
         'examples': [{'text': 'Please let me know.', 'translation': '请告诉我。'}] * 2},
        {'pattern': 'Following our phone call', 'usage': '在邮件中承接此前的电话沟通。', 'examples': []},
    ]}
    cleaned = clean_notes(data)
    assert cleaned['patterns'][0]['usage'] == ''
    assert len(cleaned['patterns'][0]['examples']) == 1
    assert cleaned['patterns'][0]['examples'][0]['translation'] == '请告诉我。'
    assert cleaned['patterns'][1] == data['patterns'][1]
    assert data['patterns'][0]['usage']
    assert clean_notes(cleaned) == cleaned
