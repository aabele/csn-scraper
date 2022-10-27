import json
import requests
import base64
import hashlib

from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)



class Question():

    def __init__(self, data):
        self.data = data

    @property
    def signature(self):
        return str(base64.b64encode(hashlib.sha256(bytes(self.get_signature_key())).digest()))

    def get_signature_key(self):
        question = self.data['text']
        answers = '|'.join(self.data['answ'])
        picture = self.data['picturedata']
        return f'{question}-{answers}-{picture}'.encode('utf8')

    @property
    def formatted(self):
        return {
            'id': self.data['questID'],
            'question': self.data['text'],
            'choices': self.data['answ'],
            'answer': self.data['answ'][int(self.data['coransw']) - 1],
            'picture': self.data['picturedata'],
            'signature': self.signature
        }


class CSN():
    host = 'https://csn.vtua.gov.lv'
    exam_endpoint = '/files/test_but1.php'
    question_endpoint = '/files/exam_questions.php'
    lang = 'lv'

    headers = {}

    def _call(self, endpoint, payload):
        response = requests.post(f'{self.host}{endpoint}', data=payload, verify=False, headers=self.headers)
        return response.json()

    def get_exam_id(self):
        data = self._call(self.exam_endpoint, { 'cat': 1, 'lang': self.lang})
        return data.get('examID');

    def get_questions(self, exam_id):
        data = self._call(self.question_endpoint, { 'action': 'questionList', 'examid': exam_id})
        return data.get('exam_questions');

    def get_question(self, exam_id, question_id):
        payload = {'action': 'examQuestion', 'examid': exam_id, 'question_id': question_id, 'lang': self.lang}
        data = self._call(self.question_endpoint, payload)
        return data

    def take_exams(self, exam_count=1):
        signatures = []
        data = []

        for exam in range(exam_count):
            print('Taking exam:', exam)
            print('-' * 80)
            exam_id = self.get_exam_id()
            questions = self.get_questions(exam_id)
            for q in questions:
                question = Question(self.get_question(exam_id, q))
                signature = question.signature
                if signature not in signatures:
                    data.append(question.formatted)
                    signatures.append(signature)

        return data

def question2html(data):
    question = data['question']
    answer = data['answer']
    choices = '</li><li>'.join(data['choices'])
    image_src = data['picture']
    image = f'<img src="{image_src}" />'
    return f'''
        <div style="page-break-before: always;">
            <h2>{question}</h3>
            <p>{image}</p>
            <h4>Atbilžu varianti</h4>
            <ul>
                <li>{choices}</li>
            </ul>
            <p><strong>Pareizā atbilde:</strong> {answer}</p>
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
    data = csn.take_exams(1000)

    html_data = as_html(data)

    with open('questions.html', 'w+') as f:
        f.write(html_data)

    with open('questions.json', 'w+') as f:
        f.write(json.dumps(data, indent=4))