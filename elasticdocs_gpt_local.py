import os
import streamlit as st
from openai import OpenAI
from elasticsearch import Elasticsearch

# This code is part of an Elastic Blog showing how to combine
# Elasticsearch's search relevancy power with 
# OpenAI's GPT's Question Answering power
# https://www.elastic.co/blog/chatgpt-elasticsearch-openai-meets-private-data

# Code is presented for demo purposes but should not be used in production
# You may encounter exceptions which are not handled in the code


# Required Environment Variables
# openai_url - OpenAI URL
# openai_api - OpenAI API key
# openai_model - OpenAI model
# local_es_url - Local ES URL
# local_es_user - Local ES User
# local_es_pwd - Local ES Password
# local_es_index - index name where data are stored


from openai import OpenAI
client = OpenAI(
    base_url = os.environ['openai_url'],
    api_key=os.environ['openai_api_key'] # required, but unused
)

# Connect to Elastic Cloud cluster
def es_connect(es_url, es_user, es_pwd):
    es = Elasticsearch(es_url, basic_auth=(es_user, es_pwd))
    return es

# Search ElasticSearch index and return body and URL of the result
def search(query_text):
    es_url = os.environ['local_es_url']
    es_user = os.environ['local_es_user']
    es_pwd = os.environ['local_es_pwd']
    es = es_connect(es_url, es_user, es_pwd)
    es_index = os.environ['local_es_index']

    query = {
        "retriever": {
            "standard": {
                "query": {
                    "nested": {
                        "path": "semantic_body.inference.chunks",
                        "query": {
                            "knn": {
                                "field": "semantic_body.inference.chunks.embeddings",
                                "query_vector_builder": {
                                    "text_embedding": {
                                        "model_id": "my-e5-model",
                                        "model_text": query_text
                                    }
                                }
                            }
                        },
                        "inner_hits": {
                            "size": 2,
                            "name": "search-elastic-labs.semantic_body",
                            "_source": [
                                "semantic_body.inference.chunks.text"
                            ]
                        }
                    }
                }
            }
        },
        "size": 5
    }
    #fields = ["title", "body_content", "url"]
    index = es_index
    resp = es.search(index=index,
                     body=query,
                     #fields=fields,
                    )
    # body = resp['hits']['hits'][0]['_source']['body_content']
    # url = resp['hits']['hits'][0]['_source']['url']

    # return body, url

    results = resp["hits"]["hits"]
    context = ""
    index_source_fields = {
        "search-elastic-labs": [
            "semantic_body"
        ]
    }
    for hit in results:
        inner_hit_path = f"{hit['_index']}.{index_source_fields.get(hit['_index'])[0]}"
        ## For semantic_text matches, we need to extract the text from the inner_hits
        if 'inner_hits' in hit and inner_hit_path in hit['inner_hits']:
            context += '\n --- \n'.join(inner_hit['_source']['text'] for inner_hit in hit['inner_hits'][inner_hit_path]['hits']['hits'])
        else:
            source_field = index_source_fields.get(hit["_index"])[0]
            hit_context = hit["_source"][source_field]
            context += f"{hit_context}\n"
    prompt = f"""
            Tu es un assistant utile et compétent conçu pour aider les utilisateurs à interroger des informations liées à la Recherche, à l'Observabilité et à la Sécurité. 
            Ton objectif principal est de fournir des réponses claires, concises et précises, basées sur des documents sémantiquement pertinents récupérés via Elasticsearch.
            **Tu dois répondre en Français uniquement.**

            ### Directives :

            #### Public cible :
            - Supposer que l'utilisateur peut avoir n'importe quel niveau d'expérience, mais privilégier une orientation technique dans les explications.
            - Éviter le jargon trop complexe, sauf s’il est courant dans le contexte d’Elasticsearch, de la Recherche, de l’Observabilité ou de la Sécurité.

            #### Structure des réponses :
            - **Clarté** : Les réponses doivent être claires et concises, sans verbiage inutile.
            - **Concision** : Fournir l’information de la manière la plus directe possible, en utilisant des puces si pertinent.
            - **Mise en forme** : Utiliser la mise en forme Markdown pour :
            - Les listes à puces afin d’organiser l’information
            - Les blocs de code pour tout extrait de code, configuration ou commande
            - **Pertinence** : L’information fournie doit être directement liée à la requête de l’utilisateur, en privilégiant la précision.

            #### Contenu :
            - **Profondeur technique** : Offrir une profondeur technique suffisante tout en restant accessible. Adapter la complexité en fonction du niveau de connaissance apparent de l'utilisateur, déduit de sa requête.
            - **Exemples** : Lorsque c’est approprié, fournir des exemples ou des scénarios pour clarifier les concepts ou illustrer des cas d’usage.
            - **Liens vers la documentation** : Lorsque cela est pertinent, proposer des ressources ou de la documentation supplémentaires depuis *Elastic.co* pour aider davantage l’utilisateur.

            #### Ton et style :
            - Maintenir un ton **professionnel** tout en étant **accessible**.
            - Encourager la curiosité en étant **bienveillant** et **patient** avec toutes les requêtes, peu importe leur complexité.

            ### Exemples de requêtes :
            - "Comment optimiser mon cluster Elasticsearch pour le traitement de données à grande échelle ?"
            - "Quelles sont les bonnes pratiques pour implémenter l'observabilité dans une architecture microservices ?"
            - "Comment sécuriser les données sensibles dans Elasticsearch ?"

            ### Règles :
            - Répondre aux questions de manière **véridique** et **factuelle**, **en se basant uniquement sur le contexte présenté ci-dessous**.
            - Si tu ne connais pas la réponse, **dis-le simplement**. Ne pas inventer de réponse.
            - Toujours **citer le document** d’où provient la réponse en utilisant le style de citation académique en ligne `[]`, avec la position.
            - Utiliser le **format Markdown** pour les exemples de code.

            Tu dois être **exact**, **fiable**, **précis** et **factuel**.

            Context:
            {context}
            
    """
    return prompt


def truncate_text(text, max_tokens):
    tokens = text.split()
    if len(tokens) <= max_tokens:
        return text

    return ' '.join(tokens[:max_tokens])

# Generate a response from ChatGPT based on the given prompt
def chat_gpt(prompt, query, max_tokens=1024, max_context_tokens=4000, safety_margin=5):
    # Truncate the prompt content to fit within the model's context length
    # truncated_prompt = truncate_text(prompt, max_context_tokens - max_tokens - safety_margin)

    response = client.chat.completions.create(model=os.environ['openai_model'], messages=[{"role": "system", "content": prompt}, {"role": "user", "content": query}])
    # print(response.choices[0].message.content)
    return response.choices[0].message.content


st.title("ElasticDocs GPT")

# Main chat form
with st.form("chat_form"):
    query = st.text_input("You: ")
    submit_button = st.form_submit_button("Send")

# Generate and display response on form submission
negResponse = "Désolé, je ne suis pas capable de vous répondre avec les informations que j'ai."
if submit_button:
    prompt = search(query)
    #prompt = f"Answer this question: {query}\nUsing only the information from this Elastic Doc: {resp}\nIf the answer is not contained in the supplied doc reply '{negResponse}' and nothing else"
    answer = chat_gpt(prompt, query)
    
    st.write(f"ChatGPT: {answer.strip()}")
