import json
import pytest
import requests
import requests_mock
import sys

IP_ADDRESS = '127.0.0.1'

FILE_RES_JSON = {
    "indicator": {
        "latestPanVerdicts": {
            "WF_SAMPLE": "MALWARE"
        }
    }
}

IP_RES_JSON = {
    "indicator": {
        "indicatorValue": IP_ADDRESS,
        "indicatorType": "IPV4_ADDRESS",
        "summaryGenerationTs": 1576077539906,
        "latestPanVerdicts": {
            "PAN_DB": "MALWARE"
        },
        "seenByDataSourceIds": [
            "WF_SAMPLE"
        ],
        "wildfireRelatedSampleVerdictCounts": {
            "MALWARE": 95,
            "GRAYWARE": 5
        }
    },
    "tags": [
        {
            "support_id": 1,
            "tag_name": "Upatre",
            "public_tag_name": "Unit42.Upatre",
            "tag_definition_scope_id": 4,
            "tag_definition_status_id": 1,
            "count": 7692947,
            "lasthit": "2019-12-11 02:29:45",
            "description": "The Upatre Trojan typically arrives as an e-mail attachment or through"
                           " an e-mail with a link to the malware. Upatre's function is to download additional"
                           " malware onto the system, in most cases when the malware was initially observed"
                           " downloading the Dyre banking Trojan which then attempts to steal the users online"
                           " banking credentials which may may be used for fraud.\n\nSince then, the operators have"
                           " diversified, with Upatre frequently seen downloading other banking trojans.\n",
            # noqa: E501
            "customer_name": "Palo Alto Networks Unit42",
            "customer_industry": "High Tech",
            "upVotes": 2,
            "downVotes": None,
            "myVote": None,
            "source": "Unit 42",
            "tag_class_id": 3,
            "tag_definition_id": 29449,
            "tagGroups": [
                {
                    "tag_group_name": "Downloader",
                    "description": "This type of malware secretly downloads malicious files from a remote server, then installs and executes the files."  # noqa: E501
                }
            ],
            "aliases": [
                "Upatre"
            ]
        }
    ]
}

INDICATOR_RES = {
    "IndicatorValue": IP_ADDRESS,
    "IndicatorType": "IPV4_ADDRESS",
    "LatestPanVerdicts": {
        "PAN_DB": "MALWARE"
    },
    "WildfireRelatedSampleVerdictCounts": {
        "MALWARE": 95,
        "GRAYWARE": 5
    },
    "SeenBy": [
        "WF_SAMPLE"
    ],
    "Tags": [
        {
            "PublicTagName": "Unit42.Upatre",
            "TagName": "Upatre",
            "CustomerName": "Palo Alto Networks Unit42",
            "Source": "Unit 42",
            "TagDefinitionScopeID": 4,
            "TagDefinitionStatusID": 1,
            "TagClassID": 3,
            "Count": 7692947,
            "Lasthit": "2019-12-11 02:29:45",
            "Description": "The Upatre Trojan typically arrives as an e-mail attachment or through an e-mail with a"
                           " link to the malware. Upatre's function is to download additional malware onto the system,"
                           " in most cases when the malware was initially observed downloading the Dyre banking Trojan"
                           " which then attempts to steal the users online banking credentials which may may be used "
                           "for fraud.\n\nSince then, the operators have diversified, with Upatre frequently"
                           " seen downloading other banking trojans.\n"
            # noqa: E501
        }
    ]
}


def test_parse_indicator_response():
    from AutofocusV2 import parse_indicator_response
    raw_indicator = IP_RES_JSON['indicator']
    raw_tags = IP_RES_JSON['tags']
    indicator = parse_indicator_response(raw_indicator, raw_tags, 'IP')
    assert json.dumps(indicator) == json.dumps(INDICATOR_RES)


def test_calculate_dbot_score():
    from AutofocusV2 import calculate_dbot_score
    raw_indicator = IP_RES_JSON['indicator']
    score = calculate_dbot_score(raw_indicator, 'IP')
    assert score == 3


def test_calculate_dbot_score_file():
    from AutofocusV2 import calculate_dbot_score
    raw_indicator = IP_RES_JSON['indicator']
    score = calculate_dbot_score(raw_indicator, 'File')
    assert score == 3


def test_connection_error(mocker):

    import AutofocusV2

    RETURN_ERROR_TARGET = 'AutofocusV2.return_error'
    BASE_URL = 'https://autofocus.paloaltonetworks.com/api/v1.0'

    return_error_mock = mocker.patch(RETURN_ERROR_TARGET, side_effect=sys.exit)

    with requests_mock.Mocker() as m:
        m.get(f'{BASE_URL}/tic', exc=requests.exceptions.ConnectionError)

        with pytest.raises(SystemExit):
            AutofocusV2.search_indicator('ip', '8.8.8.8')
        assert 'Error connecting to server. Check your URL/Proxy/Certificate settings'\
               in return_error_mock.call_args[0][0]


def test_search_ip_command(mocker):
    """
    Given
    - AF ip command
    When
    - mock the search_indicator with a malicious ip results.
    Then
    - run the search_ip_command
    Validate the indicator contains FirstSeenBySource, LastSeenBySource and Tags.
    """
    from test_data.response import MALICIOUS_IP
    import AutofocusV2
    mocker.patch.object(AutofocusV2, 'search_indicator', return_value=MALICIOUS_IP)

    command_results = AutofocusV2.search_ip_command('200.63.47.3')
    outputs = command_results.to_context().get('EntryContext', {})
    ip_outputs = outputs.get('IP(val.Address && val.Address == obj.Address)', [])[0]
    assert ip_outputs.get('FirstSeenBySource') == '2019-08-20T00:38:15.000Z'
    assert ip_outputs.get('LastSeenBySource') == '2020-05-28T03:04:19.000Z'
    assert 'TagName' in ip_outputs.get('Tags')[0].keys()
