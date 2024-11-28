"""AUTHORS: Daniel Adam, Martin Timoščuk, 2024"""
import json
import re
import datetime
import os
import replicate
from dotenv import dotenv_values
import sys
import argparse
import requests
from bs4 import BeautifulSoup
from huggingface_hub import InferenceClient
from openai import OpenAI

os.environ["REPLICATE_API_TOKEN"] = dotenv_values()["REPLICATE_API_TOKEN"]


sys.stdout.reconfigure(encoding="utf-8")

parser = argparse.ArgumentParser()
parser.add_argument('-s', '--statements', required=True, action="append")
parser.add_argument('-t', '--temperature', required=False)
parser.add_argument('-u', '--url', required=True)
parser.add_argument('-m', '--model', required=True)
parser.add_argument('-p', '--provider', required=True, choices=['replicate', 'tgi', 'webui'])
parser.add_argument('-o', '--openai_api_url', required=False)
args = parser.parse_args()

if args.provider == "tgi":
    client = InferenceClient(model=args.openai_api_url)

if args.provider == "webui":
    client = OpenAI(
        base_url=args.openai_api_url,
        api_key="-"
    )

INPUT_URL = str(args.url)
MODEL_PROVIDER = str(args.provider)
MODEL = str(args.model)
TEMPERATURE = float(args.temperature)
INPUT_STATEMENTS = []
for statement in args.statements:
    triple = statement.split(",")
    INPUT_STATEMENTS.append({
        "subject": triple[0],
        "predicate": triple[1],
        "object": triple[2]
    })

# print(args.statements)
common_prompt_settings = {
    "top_p": 0.9,
    "temperature": TEMPERATURE if TEMPERATURE else 0.1,
    "max_new_tokens": 500,
    "min_new_tokens": -1,
}

# add webarchive option to UI
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

def infer(message):
    if MODEL_PROVIDER == 'replicate':
        response = ''
        options = {'system_prompt': 'You are a helpful assistant.',
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
        completion = client.chat.completions.create(
            model="",
            messages=[
                {"role": "user", "content": message}
            ],
            temperature=TEMPERATURE if TEMPERATURE else 0.1,
            max_tokens=common_prompt_settings["max_new_tokens"]
        )
        return completion.choices[0].message.content

def get_opinion(statement, paragraph):
    rdf = 'RDF: ["{0}" - "{1}" - "{2}"]'.format(statement["subject"], statement["predicate"], statement["object"])
    message = ("Can the given RDF statement be inferred from the given snippet?\n" + rdf + "\n" +
        "Snippet: \"" + paragraph + "\"\n" +
        "Please, give an answer and also the reasoning behind it!"
    )
    return infer(message)


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


def generate_json(statement, paragraph_validations, start_time, end_time):
    finalDecision = False
    paragraphs = []
    for pv in paragraph_validations:
        paragraphs.append({
            "text": pv["paragraph"],
            "reasoning": pv["opinion"],
            "decision": pv["decision"]
        })
        if (pv["decision"]):
            finalDecision = True
    result = {
        "paragraphs" : paragraphs,
        "finalDecision": finalDecision,
        "elapsed": (start_time - end_time).total_seconds(),
        "date": start_time.strftime("%Y-%m-%d"),
        "time": start_time.strftime("%H:%M:%S"),
        "subject": statement["subject"],
        "predicate": statement["predicate"],
        "object": statement["object"],
        "model": MODEL
    }


    j = json.dumps(result)
    x = re.sub(r'\s+', ' ', j)
    return x.strip()

def main():
    paragraphs = get_paragraphs(INPUT_URL)
    json_results = []
    for statement in INPUT_STATEMENTS:
        start_time = datetime.datetime.now()
        paragraph_validations = []
        for paragraph in paragraphs:
                # print("Paragraph: " + paragraph.replace("\n", ""), flush=True)
                opinion = get_opinion(statement, paragraph)
                # print("Answer and reasoning: " + opinion.replace("\n", ""), flush=True)
                decision = get_decision(opinion)
                # print("Parsed answer: " + str(decision) + "\n", flush=True)
                paragraph_validations.append({"paragraph": paragraph, "opinion": opinion, "decision": decision})
        end_time = datetime.datetime.now()
        # xml = generate_xml(statement, paragraph_validations, start_time, end_time)
        # xml_results.append(xml)
        # print(CORE_XML_MESSAGE_PREFIX + xml)
        json = generate_json(statement, paragraph_validations, start_time, end_time)
        json_results.append(json)
        print(json, flush=True)


    # with open(f'xml/{time0.strftime("%Y-%m-%d(%Hh%Mm%Ss)")}.txt', 'w', encoding="utf-8") as f:
    #     f.write(generate_xml(results, time0, time1).replace("\n",""))

main()

# """Daniel"""
# import requests
# from bs4 import BeautifulSoup
# from pypdf import PdfReader
# import replicate
# from dotenv import dotenv_values
# import re
# import io
# from difflib import SequenceMatcher

# import json
# import datetime
# import os
# import sys
# import argparse
# from bs4 import BeautifulSoup
# from huggingface_hub import InferenceClient
# from openai import OpenAI


# from pydantic import BaseModel
# from newspaper import Article

# parser = argparse.ArgumentParser()
# parser.add_argument('-s', '--statements', required=True, action="append")
# parser.add_argument('-t', '--temperature', required=False)
# parser.add_argument('-u', '--url', required=True)
# parser.add_argument('-m', '--model', required=True)
# parser.add_argument('-p', '--provider', required=True, choices=['replicate', 'tgi', 'webui'])
# parser.add_argument('-o', '--openai_api_url', required=False)
# args = parser.parse_args()

# os.environ["REPLICATE_API_TOKEN"] = dotenv_values()["REPLICATE_API_TOKEN"]
# sys.stdout.reconfigure(encoding="utf-8")

# INPUT_URL = str(args.url)
# MODEL_PROVIDER = str(args.provider)
# MODEL = str(args.model)
# TEMPERATURE = float(args.temperature)

# INPUT_STATEMENTS = []
# for statement in args.statements:
#     triple = statement.split(",")
#     INPUT_STATEMENTS.append({
#         "subject": triple[0],
#         "predicate": triple[1],
#         "object": triple[2]
#     })

# if args.provider == "tgi": inf_client = InferenceClient(model=args.openai_api_url)
# elif args.provider == "webui": inf_client = OpenAI(base_url=args.openai_api_url, api_key="-")

# SYSTEM_PROMPT = ("You will be given a text and an RDF statement. " + 
# "Your objective is to decide whether the statement can be inferred from the given text without using external information. "
# "Respond in JSON format when specifically asked to.")

# CONTEXT_SIZE = 16384
# COMMON_PROMPT_SETTINGS = {
#     "top_p": 0.9,
#     "temperature": TEMPERATURE if TEMPERATURE else 0.5,
#     "max_new_tokens": 500,
#     "min_new_tokens": -1,
# }

# def get_current_model_name_webui():
#     return requests.get(
#         "https://llm.vse.cz/text-generation-webui/api/v1/internal/model/info",
#         headers={"Content-Type":"application/json"},
#         ).json()["model_name"]

# def get_token_count_webui(text):
#     return requests.post(
#         "https://llm.vse.cz/text-generation-webui/api/v1/internal/token-count",
#         headers={"Content-Type":"application/json"},
#         json={"text": text}
#         ).json()["length"]


# #simplified function for validating ALL text of a webpage
# def get_text_parts_from_url(url):
#     try:
#         article = Article(url)
#         article.download()
#         article.parse()
#     except Exception as e:
#         print("Error:" + str(e))
#         return []
#     max_input_tokens = CONTEXT_SIZE - COMMON_PROMPT_SETTINGS["max_new_tokens"] - len(SYSTEM_PROMPT)
#     text_parts = [article.text]
#     i = 0
#     while get_token_count_webui(text_parts[-1]) > max_input_tokens:
#         text_parts.append(text_parts[i-1][max_input_tokens:])
#         text_parts[-1] = text_parts[i-1][:max_input_tokens]
#         i += 1
#     return text_parts

# def get_paragraphs_from_url(url):
#     try:
#         r = requests.get(url, timeout=10)
#     except Exception as e:
#         print("Error: {}".format(str(e)))
#         return []
#     content_type = r.headers.get('content-type')
#     if content_type == "application/pdf":
#         f = io.BytesIO(r.content)
#         reader = PdfReader(f)
#         paragraphs = []
#         for page in reader.pages:
#             # špatné řešení, ale prozatím to šetří mnoho API requestů
#             if "References" in page.extract_text():
#                 break
#             content = page.extract_text().split('\n')
#             final = []
#             for cont in content:
#                 if len(cont) >= 50:
#                     final.append(cont)
#             paragraphs.append(" ".join(final))
#         return paragraphs
#     soup = BeautifulSoup(r.text, 'html.parser')
#     listOfParagraphs = []
#     for data in soup.find_all("p"):
#         if data.getText():
#             trimmed = ' '.join(data.getText().replace("\n", "").split())
#             if len(trimmed) >= 100:
#                 listOfParagraphs.append(trimmed)
#     return listOfParagraphs


# def infer(message, max_new_tokens, json_output=False):
    
#     def infer_webui():       
#         completion = inf_client.chat.completions.create(
#             model=get_current_model_name_webui(),
#             max_tokens=max_new_tokens,
#             n=1,
#             temperature=TEMPERATURE or 0.5,
#             stream=True,
#             response_format={ "type": "json_object"} if json_output else "text",
#             messages=[
#                 {'role': "system", "content": SYSTEM_PROMPT},
#                 {'role': 'user', 'content': message}]
#         )
#         response = ""

#         for chunk in completion:
#             response += str(chunk.choices[0].delta.content)
#             # if chunk.usage: print("received" + str(chunk.usage))
#             # tokens += chunk.usage
        
#         return response
#         # return completion.choices[0].message.content
        
#     def infer_tgi():
#         response = ''
#         for token in inf_client.text_generation(message, stream=True,
#                 max_new_tokens=max_new_tokens,
#                 temperature=TEMPERATURE or 0.5,
#                 top_p=0.9):
#             response = response + str(token)
#         return response
    
#     def infer_replicate():
#         response = ''
#         options = ({**COMMON_PROMPT_SETTINGS,
#                     "temperature": TEMPERATURE or 0.5,
#                     "max_new_tokens": max_new_tokens,
#                     'system_prompt': 'You are a helpful assistant.',
#                     'prompt': message, 'stream': True}
#         )
#         for event in replicate.stream(MODEL, options):
#             response = response + str(event)
#         return response
    
#     return (
#         infer_replicate() if MODEL_PROVIDER == 'replicate' else
#         infer_tgi() if MODEL_PROVIDER == 'tgi' else
#         infer_webui() if MODEL_PROVIDER == 'webui' else
#         Exception("Invalid model provider")
#     )


# #PROMPT 1
# def get_opinion(statement, paragraph):
#     rdf = "RDF statement: {0} {1} {2}".format(statement["subject"], statement["predicate"], statement["object"])
#     message = ("Can the given RDF statement be inferred from the given text?\n" +
#         rdf + "\n" +
#         "Text: \"" + paragraph + "\"\n" +
#         "Please, provide a boolean decison and also the reasoning behind it in JSON format: {\"decision\":boolean,\"reasoning\":string}!"
#     )
#     # print("checker-msg: opinion-prompt:", message)
#     opinion_json = infer(message, 256, True)
#     # opinion = j["opinion"]""
#     print("ipc:", opinion_json, flush=True) #
#     return json.loads(opinion_json)["decision"]




# #PROMPT 2
# def get_decision(opinion):
#     message = (
#         "Based on the following reasoning: " + opinion + "\n" +
#         "Can the given RDF statement be inferred from the given text?\n" +
#         'Answer in the JSON format: {"decision":boolean,"reasoning":string}'
#         # "Choose and explicitly name the corresponding option A) or B) based on the following reasoning: "+ opinion + "\n" +
#         # "A) The RDF statement can be inferred from the snippet.\n" +
#         # "B) The RDF statement can not be inferred from the snippet." +
#         # "Answer in JSON format: {decision:boolean}"
#     )
#     print("checker_msg: decision-prompt: " + message)
#     response = infer(message, 16, True)
#     print("checker_msg: decision_json: " + response)
    
#     # regex_check_a = re.search("(A|a)\)", response)
#     # regex_check_b = re.search("(B|b)\)", response)
    
#     # decision = (True if regex_check_a is not None else
#     #             False if regex_check_b is not None else
#     #             None)
    
#     return False

# ## tuto funkci volám, když je vrácený počet odstavců z funkce """get_paragraphs_from_url""" příliš mnoho
# ## parametr n vrátí n nejbližších odstavců řetězci spojeného ze subjektu a obejktu
# def get_similar_paragraphs(subject, object, text_chunks, n):
#     paragraphs_similarized = []
#     ratios = []
#     for p in text_chunks:
#         s = SequenceMatcher(None, f"{subject} {object}", p)
#         ratios.append([s.ratio(), p])
#     ratios.sort(reverse=True)
#     for r in ratios[:n]:
#         # print(f"{r[0]} {r[1]}")
#         paragraphs_similarized.append(r[1])
#     return paragraphs_similarized


# def main():
#     parts = get_paragraphs_from_url(INPUT_URL)
#     # print(parts[0][:128])
#     # print(infer("What is the meaning of life?", 64))
#     # print(infer("Is Nico Ditch in England?", get_token_count_webui("{final_decision: false}"), True))
        
#     # print(get_opinion({'subject': 'two plus two', 'predicate': 'equals', 'object': 'four'}, "It is a fact that 2 + 2 equals 4."))
#     # parts = ["""Nico Ditch is a six-mile (9.7 km) long linear earthwork between Ashton-under-Lyne and Stretford in Greater Manchester, England. It was dug as a defensive fortification, or possibly a boundary marker, between the 5th and 11th century. The ditch is still visible in short sections, such as a 330-yard (300 m) stretch in Denton Golf Course. For the parts which survived, the ditch is 4–5 yards (3.7–4.6 m) wide and up to 5 feet (1.5 m) deep. Part of the earthwork is protected as a Scheduled Ancient Monument.""", """Etymology
# # The earliest documented reference to the ditch is in a charter detailing the granting of land in Audenshaw to the monks of the Kersal Cell. In the document, dating from 1190 to 1212, the ditch is referred to as "Mykelldiche", and a magnum fossatum, which is Latin for "large ditch".[1]"""]
    
#     opinions = []
#     decisions = []
#     statement = INPUT_STATEMENTS[0]
#     opinions.append(get_opinion(statement, parts[0]))
#     # d = get_decision(o)
#     # decisions.append(d)
    
#     return 0

# main()