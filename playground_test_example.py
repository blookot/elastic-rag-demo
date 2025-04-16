## Install the required packages
## pip install -qU elasticsearch openai
import os
from elasticsearch import Elasticsearch
from openai import OpenAI

es_pwd = os.environ['local_es_pwd']
es_client = Elasticsearch(
    'http://localhost:9200',
    basic_auth=('elastic', es_pwd)
)
openai_client = OpenAI(
    base_url = 'http://localhost:11434/v1',
    api_key='whatever'
)
query = "Peux-tu m'aider à mettre en place de la recherche sémantique augmentée (RAG) avec Elasticsearch ?"

index_source_fields = {
    "search-elastic-labs": [
        "semantic_body"
    ]
}
def get_elasticsearch_results():
    es_query = {
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
                                        "model_text": query
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
        "size": 3
    }
    result = es_client.search(index="search-elastic-labs", body=es_query)
    return result["hits"]["hits"]
def create_openai_prompt(results):
    context = ""
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
- Répondre aux questions de manière **véridique** et **factuelle**, en se basant uniquement sur le contexte présenté.
- Si tu ne connais pas la réponse, **dis-le simplement**. Ne pas inventer de réponse.
- Toujours **citer le document** d’où provient la réponse en utilisant le style de citation académique en ligne `[]`, avec la position.
- Utiliser le **format Markdown** pour les exemples de code.

Tu dois être **exact**, **fiable**, **précis** et **factuel**.

  Context:
  {context}
  
  """
    return prompt
def generate_openai_completion(user_prompt, question):
    response = openai_client.chat.completions.create(
        model="mistral",
        messages=[
            {"role": "system", "content": user_prompt},
            {"role": "user", "content": question},
        ]
    )
    return response.choices[0].message.content
if __name__ == "__main__":
    question = "Peux-tu m'aider à mettre en place de la recherche sémantique augmentée (RAG) avec Elasticsearch ?"
    elasticsearch_results = get_elasticsearch_results()
    context_prompt = create_openai_prompt(elasticsearch_results)
    openai_completion = generate_openai_completion(context_prompt, question)
    print(openai_completion)