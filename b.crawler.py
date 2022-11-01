import json
import requests
import base64
import hashlib
from parsel import Selector

from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


class QuestionParser():

    def __init__(self, html):
        self.html = html
        self.selector = Selector(str(html))

    def _get_question(self):
        question = self.selector.css('h3::text').get()
        return question

    def _get_question_id(self):
        element = self.selector.css('input[name="exj_id"]')
        return element.xpath('.//@value').get()

    def _get_ece_id(self):
        element = self.selector.css('input[name="ece_id"]')
        return element.xpath('.//@value').get()

    def _get_eceja_id(self):
        element = self.selector.css('input[name="ece_id"]')
        return element.xpath('.//@value').get()

    def _get_question_id(self):
        element = self.selector.css('input[name="exj_id"]')
        return element.xpath('.//@value').get()

    def _get_multimedia(self):
        video = self.selector.css('video source').xpath('.//@src').get()
        if video:
            return video

        picture = self.selector.css('div.content-container').xpath('.//@style').get()
        if picture:
            return picture.split('\'')[1]

        return None

    def _get_answers(self):
        answers = []
        elements = self.selector.css('form label')
        for element in elements:
            answers.append({
                'text': element.xpath('.//text()[preceding-sibling::input]').get().replace('\t', '').replace('\n', ''),
                'id': element.xpath('.//input').xpath('.//@value').get()
            })
        return answers

    def as_json(self):
        return {
            'question': self._get_question(),
            'question_id': self._get_question_id(),
            'ece_id': self._get_ece_id(),
            'eceja_id': self._get_eceja_id(),
            'answers': self._get_answers(),
            'multimedia': self._get_multimedia(),
        }


class CSN():
    host = 'https://csnt2.csdd.lv'
    select_category_endpoint = '/sbm_kat'
    question_endpoint = '/LAT'
    test_answer_endpoint = '/LAT/parb_ins'
    answer_endpoint = '/LAT/atb_ins'

    category_b = '52'
    language_lat = 'LAT'

    headers = {}

    def _reset_session(self):
        self.session = requests.Session()

    def _call(self, endpoint, payload={}, update=False, json=False):
        method = 'post' if update else 'get'
        config = {
            'json' if json else 'data': payload,
            'verify': False,
            'headers': self.headers,
        }
        response = getattr(self.session, method)(f'{self.host}{endpoint}', **config)
        return response

    def select_category(self):
        payload = {
            'perform': 'confirm',
            'ext_id' : self.category_b,
            'valoda': self.language_lat,
        }
        return self._call(self.select_category_endpoint, payload=payload, update=True)

    def get_correct_answer_id(self, question, correct=None):
        question_payload = {
            "perform": "confirm",
            'exj_id': question['question_id'],
        }
        if question['ece_id']:
            question_payload['ece_id'] = question['ece_id']
            question_payload['eceja_id'] = question['eceja_id']
        sent_answer = None
        for i, answer in enumerate(question['answers']):
            question_payload[f'atbildes[{i}][exa_id]'] = answer['id']
            if (correct):
                question_payload[f'atbildes[{i}][sel]'] = 'true' if answer['id'] == correct else 'false'
            else:
                if i == 0:
                    sent_answer = answer['id']
                question_payload[f'atbildes[{i}][sel]'] = 'true' if i == 0 else 'false'

        endpoint = self.answer_endpoint if question['ece_id'] else self.test_answer_endpoint
        response = self._call(endpoint, payload=question_payload, update=True)
        if correct:
            return

        correct_answer_id = 'Šī ir pareizā atbilde.'

        response_data = response.json()
        if response_data['errors']:
            errors = response_data['errors']
            for error in errors.split('\n\n\t\t'):
                if correct_answer_id in error:
                    error = error.split('$("#atbilde-')[1].split('").before')[0]
                    self.get_correct_answer_id(question, correct=error)
                    return error
            return None
        else:
            return sent_answer

    def get_question(self):
        data = self._call(self.question_endpoint)
        data = QuestionParser(data.text)
        base_data = data.as_json()
        base_data['answer'] = self.get_correct_answer_id(base_data)
        return base_data

    def take_exams(self, exam_count=1):
        signatures = []
        data = []

        for exam in range(exam_count):
            print('-' * 80)
            print('Taking exam:', exam)
            self._reset_session()
            self.select_category()

            for _ in range(30):
                question = self.get_question()
                signature = question['question_id']
                if signature and signature not in signatures:
                    data.append(question)
                    signatures.append(signature)

        return data

def download(url):
    request = requests.get(url, allow_redirects=True)
    with open(f'multimedia/{url.split("/")[-1]}', 'wb') as f:
        f.write(request.content)

def question2html(data):
    question = data['question']
    choices = '</li><li>'.join([f'{x["id"]}: {x["text"]}' for x in data['answers']])
    image_src = data['multimedia']
    image = f'<img src="{image_src}" />'
    return f'''
        <div style="page-break-before: always;">
            <h2>{question}</h3>
            <p>{image}</p>
            <h4>Atbilžu varianti</h4>
            <ul>
                <li>{choices}</li>
            </ul>
            <p><strong>Pareizā atbilde:</strong> {data['answer']}</p>
        </li>
    '''

def as_html(data):
    html_data = list(map(question2html, data))
    html_template = f"""<html>
        <head>
            <link href='http://fonts.googleapis.com/css?family=Roboto' rel='stylesheet' type='text/css'>
            <style>
                body {{
                    font-family: 'Roboto', sans-serif;
                    font-size: xx-large;
                }}
            </style>
        </head>
        <body>
            <h1>VTUA jautājumi traktoristiem</h1>
            <p>Datu avots: https://csn.vtua.gov.lv/</p>
            <p>Jautājumu skaits: {len(html_data)}</p>
            {''.join(html_data)}
        </body>
    </html>
    """
    return html_template

if __name__ == '__main__':
    csn = CSN()

    data = csn.take_exams(10)

    html_data = as_html(data)

    with open('b.questions.html', 'w+') as f:
        f.write(html_data)

    with open('b.questions.json', 'w+') as f:
        f.write(json.dumps(data, indent=4))

    [download(x['multimedia']) for x in data if x['multimedia']]
