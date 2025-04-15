# elastic-rag-demo

This repo will build a local demo of semantic search with RAG (etrieval augmented generation) using the Elastic stack and Streamlit.
For the content, we will crawl the Elastic Labs blog posts to have some private data.

This generative AI demo has been adapted from Jeff's excellent blog posts (see refs below) with a few changes:
* I wanted to run everything locally, so the Elastic stack and the LLM run locally,
* I wanted to have multilingual support, so the demo uses the e5.small embedding model (instead of Elastic's default ELSER) to support multilingual search. The examples will be in French.

Note: this is for demo purpose only! This deployment is not secure, so do not use it in production or with confidential data!


## Requirements

This demo requires a strong Linux instance with (I would say) 12+ GB RAM. I personnaly run it on a MacBook Pro (48GB RAM)...
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
Then we initialize the docker compose:
```
cd start-local
./start-local.sh -v 8.17.4
```
Do capture the output of the script, specially the elastic password!

Now we customize the docker compose file and the env file to add more RAM to Elasticsearch (for ML) and setup Enterprise Search:
```
cd elastic-start-local
sed -i -e 's/ES_LOCAL_HEAP_MAX=2g/ES_LOCAL_HEAP_MAX=8g/g' .env
echo -e "ENTERPRISE_SEARCH_LOCAL_CONTAINER_NAME=enterprise-search-local-dev\nENTERPRISE_SEARCH_PORT=3002\nMEM_LIMIT=4294967296\nENCRYPTION_KEYS=secret" >> .env
mv docker-compose.yml docker-compose.yml.backup
cp ../../docker-compose-with-enterprisesearch.yml ./docker-compose.yml
docker compose restart
cd ../../
```

## Setup a local LLM

Download & install [ollama](https://github.com/ollama/ollama) for your platform.
Get the model you want. I personnaly used mistral but I also tested ollama 3.2 which works great as well! And you can choose any of the models from [ollama library]
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
Now, save the last 3 lines of the output of the key generation command and add them to the .env file with the following commands.
Replace the 3 example keys below with your values!
```
cd start-local/elastic-start-local
echo "KIBANA_SO_KEY=2294adc7deefbf08cee931a6d059241c" >> .env
echo "KIBANA_REP_KEY=397d32d7123d7044e21d08bb2c8cdaf6" >> .env
echo "KIBANA_SEC_KEY=aff8bce5b48618b6ee77e37925f4174b" >> .env
```
Finally restart the stack:
```
docker compose restart
cd ../../
```

# Get data in!

## Create inference endpoint

Go to Kibana>Dev Tools and run (by clicking the play icon right next to the query, or press ctrl (or command) + enter):
```
PUT _inference/text_embedding/my-e5-model
{
  "service": "elasticsearch",
  "service_settings": {
    "num_threads": 1,
    "model_id": ".multilingual-e5-small",
    "adaptive_allocations": {
      "enabled": true,
      "min_number_of_allocations": 1,
      "max_number_of_allocations": 8
    }
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

Go to Kibana > Elasticsearch > Content > Web Crawlers.
Click 'Create a new web crawler'.
Name it (search-)elastic-labs and click 'Create index'.
Click the 'Mappings' tab and click 'Add field'.
Select 'Semantic text' in the field type, 'body_content' as reference field and 'semantic_body' as new field name. Change to 'my-e5-model' as inference endpoint and click the button 'Add field'.
Click the green button 'Save mapping'.

Now let's configure the domains to crawl.
In the 'Manage domains' tab, click 'Add domain'.
Enter `https://www.elastic.co/search-labs` and click 'Validate'.
After the checks run, click 'Add domain'. 
Click 'Add entry point' and enter `/security-labs` then click Save.
Repeat for `/observability-labs`
Click the 'Crawl rules' tab. Click 'Add crawl rule' and enter `Disallow` policy, regex rule `.*/author/.*` as pattern, then click 'Save'.

Click the 'Crawl' button and 'Crawl all domains on this index'.
Progress can be watched in the crawler UI and also in Kibana > Dev Tools:
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

Connectors are handled by Kibana, which in our case, is executed inside a container and needs to interact with ollama, executed on the host. For Kibana to reach ollama, we will need to use the following host: `host.docker.internal`
Note: the connector is expecting an API Key configured to work. Ollama doesn't provide this feature so you can enter a random string and save the connector.

Open Kibana and connect with the username 'elastic' and the password you captured earlier.
Go to Kibana > Stack Management > Connectors > Create connector > OpenAI

Configure the connector with For Mistral this will look like this:
![Mistral config](https://github.com/blookot/elastic-rag-demo/mistral-connector.png)

with this setup: 
* connector name: `mistral`
* OpenAI provider: `OpenAI`
* URL: `http://host.docker.internal:11434/v1/chat/completions`
* Default model: `mistral`
* API key: `whatever` (not used, but mandatory)


## Test with Playground

We will first test querying with the Kibana Playground.
Go to Kibana > Elasticsearch > Playground.
Click 'Data' and select the `search-elastic-labs` index and 'Save'.
In the bottom query bar, ask for example: "How can I use the OpenAI service for semantic search in Elasticsearch?"
You should get an answer :-)


# Adding a chat UI

Playground is great, but it's inside Kibana, and pretty limited in UX. Let's run our search outside in a dedicated chatbot UI!

## Test in a simple py file (optional)

We can first run the code that Playground can generate for us. This step is optional, you can skip it if you like.

In Playground, click the 'View code' blue button and copy the code in a py file named 'playground_test.py'.
Open this file in a text editor.
You may replace the first lines of the script with:
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
```
Note: now it's the py script calling ollama, so we use localhost in the ollama URL.

In the openai_client.chat.completions.create function call, replace `model=gpt-4o` by `model=mistral`.
Save and close the playground_test.py file.

Then go back to your terminal and enter:
```
python -m venv ./
pip install elasticsearch openai
# set the env var
export local_es_pwd="pvZ2ywkZ"
# run it
python3 playground_test.py
```

If you're happy, simply close this test:
```
deactivate
rm -rf venv
```

## Use Streamlit to power a UI

integrate this code in any UI you like! Here we're using streamlit.
Note: in the `export local_es_pwd` command, replace the random value here with your elastic password!
Note2: now that it's the py script calling ollama, we use `localhost` in the ollama URL.

```
# install required libs with
python -m venv ./
pip install -r requirements.txt
# set the env var
export openai_url="http://localhost:11434/v1"
export openai_model="mistral"
export openai_api_key="whatever"
export local_es_url="http://localhost:9200"
export local_es_user="elastic"
export local_es_pwd="pvZ2ywkZ"
export local_es_index="search-elastic-labs"
# run it
streamlit run elasticdocs_gpt_local.py
```

## Have fun querying Elastic labs!
You could ask for example (in French why not!): 
* "Peux-tu m'aider à mettre en place de la recherche sémantique augmentée (RAG) avec Elasticsearch ?" !!


## Authors

* **Vincent Maury** - *Initial commit* - [blookot](https://github.com/blookot)

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE.md](LICENSE.md) file for details
