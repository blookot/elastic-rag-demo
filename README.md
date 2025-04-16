# Elastic RAG Demo

This repo will help you build a local demo of semantic search with RAG (retrieval augmented generation) using the Elastic stack and Streamlit.<br/>
For the content, we will crawl the Elastic Labs blog posts to have some data to pass as context to the LLM.

This generative AI demo has been adapted from Jeff's excellent blog posts (see refs below) with a few changes:
* I wanted to run everything locally, so the Elastic stack and the LLM are local,
* I wanted to have multilingual support, so the demo uses the e5.small embedding model (instead of Elastic's default ELSER) to support multilingual search. The examples will be in French.

Note: this is for demo purpose only! This deployment is not secure, so do not use it in production or with confidential data!


## Requirements

This demo requires a strong Linux instance with (I would say) 12+ GB RAM. I personnaly run it on a MacBook Pro (48GB RAM)...<br/>
This demo has been tested on Elastic v8.17.4


## Refs

This demo uses:
* Elastic start-local ([ref](https://github.com/elastic/start-local)) that we will modify to add an enterprise search node,
* The first RAG demo ([blog post](https://www.elastic.co/search-labs/blog/chatgpt-elasticsearch-openai-meets-private-data) and [github repo](https://github.com/jeffvestal/ElasticDocs_GPT)) and the second updated one ([blog post](https://www.elastic.co/search-labs/blog/chatgpt-elasticsearch-rag-enhancements) and [github repo](https://github.com/jeffvestal/rag-really-tied-the-app-together)) from my colleague Jeff Vestal,
* A local LLM demo ([ref](https://github.com/fred-maussion/demo_local_ia_assistant)) based on ollama from my colleague Frédéric Maussion.


# Setup pre-requisites

We will start a local Elasticsearch + Kibana + EnterpriseSearch stack and setup a local LLM with ollama.

## Clone this repo

Open your terminal and clone this repo first:
```
git clone https://github.com/blookot/elastic-rag-demo
cd elastic-rag-demo
```

## Start a local Elastic stack

We will first deploy an Elastic stack using start-local.
Run this in your terminal:
```
./start-local.sh -v 8.17.4
```
Do capture the output of the script, specially the elastic password!

Now we customize the docker compose file and the env file to add more RAM to Elasticsearch (for ML) and setup Enterprise Search:
```
cd elastic-start-local
docker compose stop
echo -e "ENTERPRISE_SEARCH_LOCAL_CONTAINER_NAME=enterprise-search-local-dev\nENTERPRISE_SEARCH_PORT=3002\nMEM_LIMIT=8589934592\nENCRYPTION_KEYS=secret" >> .env
mv docker-compose.yml docker-compose.yml.backup
cp ../docker-compose-with-enterprisesearch.yml ./docker-compose.yml
docker compose up --wait
cd ..
```

## Setup a local LLM

Download & install [ollama](https://github.com/ollama/ollama) for your platform.<br/>
Get the model you want. I personnaly used mistral but I also tested ollama 3.2 which works great as well!<br/>
And you can choose any of the models from [ollama library](https://ollama.com/library?sort=popular) that has the 'tools' tag.
```
ollama pull mistral
ollama create gpt-4o -f Modelfile-Mistral
```

Test your new LLM (setting the model to the model you chose of course, mistral in my example):
```
curl http://localhost:11434/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "mistral",
        "messages": [
            {
                "role": "system",
                "content": "Tu es un assistant français qui donne des réponses concises."
            },
            {
                "role": "user",
                "content": "Bonjour !"
            }
        ]
    }'
```

In order to be able to use Kibana connectors, you will need to generate encryption keys from kibana docker
```
docker exec -ti kibana-local-dev bash
kibana@1d5263e8d004:~$ bin/kibana-encryption-keys generate
exit
```
Now, save the last 3 lines of the output of the key generation command and add them to the .env file with the following commands.<br/>
Replace the 3 example keys below with your values!
```
cd elastic-start-local
docker compose stop
echo "KIBANA_SO_KEY=423c22daa182e278c17c216b3db72f67" >> .env
echo "KIBANA_REP_KEY=d5a36870a7fb3fc766f6ac76cc763b49" >> .env
echo "KIBANA_SEC_KEY=b0074b7b9215c997792ad2f8bdbc3de9" >> .env
```
Finally restart the stack:
```
docker compose up --wait
cd ..
```


# Get data in!

Let's [open Kibana](http://localhost:5601/) and connect with the elastic account (and the password captured earlier), then create our inference endpoint, the web crawler and the LLM connector to play.

## Create inference endpoint

Here, we use e5.small text embedding model shipped by default with Elastic (see [doc](https://www.elastic.co/guide/en/machine-learning/current/ml-nlp-e5.html)).<br/>
We create an inference endpoint that will be used to vectorize the body of all blog posts.

Go to Kibana > Dev Tools, dismiss messages, delete everything in the left pane and run (by clicking the play icon right next to the query, or press ctrl (or command) + enter):
```
PUT _inference/text_embedding/my-e5-model
{
  "service": "elasticsearch",
  "service_settings": {
    "num_allocations": 2,
    "num_threads": 1,
    "model_id": ".multilingual-e5-small"
  }
}
```

Test using:
```
GET _inference/text_embedding/my-e5-model
POST _inference/text_embedding/my-e5-model
{
  "input": "Elastic (ESTC) est une société qui développe des logiciels de recherche et d'analyse de données. La Stack Elastic est un ensemble d'outils open source qui permettent aux entreprises d'explorer et de visualiser de grandes quantités d'informations.  Elasticsearch, Kibana et Logstash sont les composants principaux de cette suite, utilisée pour des applications variées comme la recherche, l'observabilité, la sécurité et l'analyse de données en général."
}
```


## Create the web crawler

Go to Kibana > Elasticsearch > Content > Web Crawlers.<br/>
Click 'Create a new web crawler'.<br/>
Name it (search-)elastic-labs and click 'Create index'.

Click the 'Mappings' tab and click 'Add field'.<br/>
Select 'Semantic text' in the field type, 'body_content' as reference field and 'semantic_body' as new field name. Change to 'my-e5-model' as inference endpoint and click the button 'Add field'.<br/>
See illustration below:

<p align="center">
<img src="https://github.com/blookot/elastic-rag-demo/blob/main/semantic-field.jpg" width="80%" alt="Semantic field"/>
</p>

Click the green button 'Save mapping'.

Now let's configure the domains to crawl.<br/>
In the 'Manage domains' tab, click 'Add domain'.<br/>
Enter `https://www.elastic.co/search-labs` and click 'Validate'.<br/>
After the checks run, click 'Add domain'. 

Click 'Add entry point' and enter `/security-labs` then click 'Save'.<br/>
Repeat for `/observability-labs`

Click the 'Crawl rules' tab. Click 'Add crawl rule' and enter:<br/>
`Disallow` policy, `Regex` rule, and `.*/author/.*` as pattern<br/>
Then click 'Save'.

Click the 'Crawl' button at the top right, and 'Crawl all domains on this index'.

Go back to the 'Overview' tab. You will see crawling start and the 'Document count' slowly increase.

Progress can also be watched in Kibana > Dev Tools:
```
GET /search-elastic-labs/_search
{
  "size": 0,
  "aggs": {
    "url_path_dir1": {
      "terms": {
        "field": "url_path_dir1"
      }
    }
  }
}
```


## Create the LLM connector

Connectors are handled by Kibana, which in our case, is executed inside a container and needs to interact with ollama, executed on the host. For Kibana to reach ollama, we will need to use the following host: `host.docker.internal`<br/>
Note: the connector is expecting an API Key configured to work. Ollama doesn't provide this feature so you can enter a random string and save the connector.

Open Kibana and connect with the username 'elastic' and the password you captured earlier.<br/>
Go to Kibana > Stack Management > Connectors > Create connector > OpenAI

Configuring the connector for Mistral will look like this:

<p align="center">
<img src="https://github.com/blookot/elastic-rag-demo/blob/main/mistral-connector.png" width="80%" alt="Mistral config"/>
</p>

with this setup: 
* Connector name: `Mistral`
* OpenAI provider: `OpenAI`
* URL: `http://host.docker.internal:11434/v1/chat/completions`
* Default model: `mistral`
* API key: `whatever` (not used, but mandatory)

Click the 'Save & Test' button, and on the 'Test' tab, click the 'Run' button to validate the connector is well configured.<br/>
Then 'Close' at the buttom of the pane.


## Test with Playground

We will first test querying with the Kibana Playground.

Go to Kibana > Elasticsearch > Playground.<br/>
Click the 'Data' button and select the `search-elastic-labs` index and 'Save & Continue'.<br/>
Set 'You are an assistant!' as instructions.<br/>
The infered field 'semantic_body' is automatically selected.<br/>
In the bottom query bar, type "Hello!" to start with!
You should get an answer :-)

You can switch to French, setting the instructions:<br/>
"Tu es un assistant conversationnel qui répond en Français."<br/>
And then ask for example:<br/>
"Peux-tu m'aider à mettre en place de la recherche sémantique augmentée (RAG) avec Elasticsearch ?"

Note: if you get a 10s timeout, you may need to increase the number of allocations of your inference endpoint to 4 allocations. Try to run this in Kibana > Dev Tools:
```
PUT _inference/text_embedding/my-e5-model/_update
{
  "service_settings": {
    "num_allocations": 4,
    "num_threads": 1,
    "model_id": ".multilingual-e5-small"
  }
}
```


# Adding a chat UI

Playground is great, but it's inside Kibana, and pretty limited in UX. Let's run our search outside of Kibana, in a dedicated chatbot UI!

## Test in a simple py file (optional)

We can first run the code that Playground can generate for us. This step is optional, you can skip it if you like.

In Playground, click the 'View code' blue button and copy the code (with the little copy icon) in a py file named 'playground_test.py'.<br/>
Open this file in a text editor.<br/>

There are 4 changes to be made.

1/ You may replace the first lines of the script (between `from openai import OpenAI` and `index_source_fields =...`) with:
```
es_pwd = os.environ['local_es_pwd']
es_client = Elasticsearch(
    'http://localhost:9200',
    basic_auth=('elastic', es_pwd)
)
openai_client = OpenAI(
    base_url = 'http://localhost:11434/v1/chat/completions',
    api_key='whatever'
)
query = "Peux-tu m'aider à mettre en place de la recherche sémantique augmentée (RAG) avec Elasticsearch ?"
```
Note: now it's the py script calling ollama, so we use localhost in the ollama URL.

2/ We'll also change the instructions to have them in French!
After the `prompt = f"""` line and before the `Context: {context} """` line, replace everything with this big instruction block:

```
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
```

3/ In the openai_client.chat.completions.create function call, replace `model=gpt-4o` by `model=mistral`.

4/ Finally, in the main at the bottom of the file, change the question to `question = "Peux-tu m'aider à mettre en place de la recherche sémantique augmentée (RAG) avec Elasticsearch ?"`.

Save and close the playground_test.py file.

Note: if you have any issue editing this file, you can refer to the provided playground_test_example.py and compare with yours, or simply run it.

Then go back to your terminal, replace the password below with yours, and run:
```
python -m venv .venv
source .venv/bin/activate
pip install elasticsearch==8.17.2 openai
# set the env var
export local_es_pwd="pzP0fKaw"
# run it
python3 playground_test.py
```

If you're happy, simply close this test:
```
deactivate
rm -rf .venv
```

## Use Streamlit to power a UI

Now that we know it works, we can integrate this code in a dedicated UI! Here we're using [Streamlit](https://github.com/streamlit/streamlit).

Note: in the `export local_es_pwd` command below, replace the random value with your elastic password!<br/>
Note2: now that it's the py script calling ollama, we use `localhost` in the ollama URL.

```
# install required libs in a venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# set the env var
export openai_url="http://localhost:11434/v1"
export openai_model="mistral"
export openai_api_key="whatever"
export local_es_url="http://localhost:9200"
export local_es_user="elastic"
export local_es_pwd="pzP0fKaw"
export local_es_index="search-elastic-labs"
# run it
streamlit run elasticdocs_gpt_local.py
```

Then connect to the UI via the 'Local URL' displayed in the output of the streamlit command (which should be [this URL](http://localhost:8501/)).<br/>
You should see something like this:

<p align="center">
<img src="https://github.com/blookot/elastic-rag-demo/blob/main/streamlit-screenshot.jpg" width="80%" alt="Strealit screenshot"/>
</p>

You could ask for example (in French in our example!): 
* "Comment optimiser mon cluster Elasticsearch pour le traitement de données à grande échelle ?"
* "Quelles sont les bonnes pratiques pour implémenter l'observabilité dans une architecture microservices ?"
* "Comment sécuriser les données sensibles dans Elasticsearch ?"
* "Peux-tu m'aider à mettre en place de la recherche sémantique augmentée (RAG) avec Elasticsearch ?"
* "Quelles API Elasticsearch dois-je utiliser pour utiliser un champ semantic_text ?"

Once you've finished testing, you can remove the virtual environment:
```
deactivate
rm -rf .venv
```


## Authors

* **Vincent Maury** - *Initial commit* - [blookot](https://github.com/blookot)

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE.md](LICENSE.md) file for details
