"""Daniel"""
"""
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
import io
from difflib import SequenceMatcher


def get_paragraphs_from_url(url):
    try:
        r = requests.get(url, timeout=10)
    except Exception as e:
        print("Error: {}".format(str(e)))
        return []

    content_type = r.headers.get('content-type')
    if content_type == "application/pdf":
        f = io.BytesIO(r.content)
        reader = PdfReader(f)
        paragraphs = []
        for page in reader.pages:
            # špatné řešení, ale prozatím to šetří mnoho API requestů
            if "References" in page.extract_text():
                break
            content = page.extract_text().split('\n')
            final = []
            for cont in content:
                if len(cont) >= 50:
                    final.append(cont)
            paragraphs.append(" ".join(final))
        return paragraphs


    soup = BeautifulSoup(r.text, 'html.parser')
    listOfParagraphs = []
    for data in soup.find_all("p"):
        if data.getText():
            trimmed = ' '.join(data.getText().replace("\n", "").split())
            if len(trimmed) >= 100:
                listOfParagraphs.append(trimmed)
    return listOfParagraphs


## tuto funkci volám, když je vrácený počet odstavců z funkce """get_paragraphs_from_url""" příliš mnoho
## parametr n vrátí n nejbližších odstavců řetězci spojeného ze subjektu a obejktu
def get_similar_paragraphs(subject, object, text_chunks, n):
    paragraphs_similarized = []
    ratios = []
    for p in text_chunks:
        s = SequenceMatcher(None, f"{subject} {object}", p)
        ratios.append([s.ratio(), p])
    ratios.sort(reverse=True)
    for r in ratios[:n]:
        # print(f"{r[0]} {r[1]}")
        paragraphs_similarized.append(r[1])
    return paragraphs_similarized
"""






"""Martin"""
"""INPUT_URL = ""
MODEL_PROVIDER = "" #webui/tgi/replicate
MODEL = "" #modelID
TEMPERATURE = 0.5
INPUT_STATEMENTS = []

common_prompt_settings = {
    "top_p": 0.9,
    "temperature": TEMPERATURE if TEMPERATURE else 0.1,
    "max_new_tokens": 500,
    "min_new_tokens": -1,
}

#PARSING
def get_paragraphs(url):
    r = requests.get(url).text
    soup = BeautifulSoup(r, 'html.parser')
    paragraphs = []
    for data in soup.find_all("p"):
        if "The Wayback Machine has not archived that URL." in data.getText():
            print("Error: No paragraphs found in given resource URL.", flush=True)
            quit(1)
        if data.getText() and len(data.getText()) >= 100:
            paragraphs.append(data.getText())
    isWebArchive = re.search("web.archive", url)
    if len(paragraphs) == 0 and not isWebArchive:
        paragraphs = get_paragraphs("https://web.archive.org/web/" + url)
    if len(paragraphs) == 0:
        print("Error: No paragraphs found in given resource URL.", flush=True)
        quit(1)
    return paragraphs

#INFERENCE
def infer(message):
    if MODEL_PROVIDER == 'replicate':
        response = ''
        options = {**common_prompt_settings, 'system_prompt': 'You are a helpful assistant.',
                   'prompt': message, 'stream': True}
        for event in replicate.stream(MODEL, options):
            response = response + str(event)
        return response
    elif MODEL_PROVIDER == 'tgi':

        response = ''
        for token in client.text_generation(message, stream=True,
                max_new_tokens=500,
                temperature=(TEMPERATURE if TEMPERATURE else 0.1),
                top_p=0.9):
            response = response + str(token)
        return response
    elif MODEL_PROVIDER == 'webui':

        completion = client.chat.completions.create(model='',
                messages=[{'role': 'user', 'content': message}, {'role': 'system', 'content': 'You are a helpful assistant.'}])
        return completion.choices[0].message.content
            
#PROMPT 1
def get_opinion(statement, paragraph):
    rdf = 'RDF: ["{0}" - "{1}" - "{2}"]'.format(statement["subject"], statement["predicate"], statement["object"])
    message = ("Can the given RDF statement be inferred from the given snippet?\n" + rdf + "\n" +
        "Snippet: \"" + paragraph + "\"\n" +
        "Please, give an answer and also the reasoning behind it!"
    )
    return infer(message)

#PROMPT 2
def get_decision(opinion):
    message = (
        "Choose and explicitly name the corresponding option A) or B) based on the following reasoning: "+ opinion + "\n" +
        "A) The RDF statement can be inferred from the snippet.\n" +
        "B) The RDF statement can not be inferred from the snippet."
    )
    response = infer(message)
    regex_check_a = re.search("(A|a)\)", response)
    regex_check_b = re.search("(B|b)\)", response)    
    if (regex_check_a is not None): return True
    if (regex_check_b is not None): return False
