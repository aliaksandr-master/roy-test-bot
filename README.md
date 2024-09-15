# Roy FAQ bot

semantic search with your documents

Integrations:
- [Roy.team](Roy.team)
- [Notion.so](Notion.so)

## How to setup your own FAQ bot on your infrastructure
1. register in [GitHub.com](GitHub.com)
2. make a fork of this project [roy-test-bot](https://github.com/aliaksandr-master/roy-test-bot)
3. register in [DigitalOcean.com](https://www.digitalocean.com/?refcode=a7a63e8dfa85) use this referral link for get free money on 2 months period

### AppPlatform on digitalocean.com
create new App in App Platform user [this instruction](https://docs.digitalocean.com/products/app-platform/how-to/create-apps/)

1. go to App Platform https://cloud.digitalocean.com/apps
2. make new application. make uniq name
3. In settings:
    1. in repository set GitHub-link on your own fork OR original repo [https://github.com/aliaksandr-master/roy-test-bot](https://github.com/aliaksandr-master/roy-test-bot)
    2. branch - `dev` (or your variant if you changed the repo)
    3. path set as is - `/`
4. Chose the cheapest resource for example instance for $5 (no reason to set it to something else)
5. In settings of component set environment variables in section **`Environment Variables`**
    - `SRC_NOTION_API_KEY` - optional - notion api key [create integration first with this manual](https://developers.notion.com/docs/create-a-notion-integration) - just copy `secret-key`
    - `SRC_NOTION_WIKI_ID` - optional - notion db id (id of root wiki page) ([manual](https://stackoverflow.com/questions/67728038/where-to-find-database-id-for-my-database-in-notion))
    - `BOT_API_KEY` - required - create application with BotFather ([manual video](https://www.youtube.com/watch?v=UQrcOj63S2o))
    - `LLM_OPENAI_API_KEY` - required - create openai api key ([manual](https://platform.openai.com/docs/quickstart/create-and-export-an-api-key))
    - `LLM_OPENAI_MODEL_NAME` - default="gpt-3.5-turbo-0125" - openAI model name ([see here](https://platform.openai.com/docs/models))
    - `SRC_ROY_ORG_ID` - optional - organization for getting some materials
    - `SRC_ROY_SECTIONS` - optional - comma-divided numbers of sections for filter materials in organizations
    - `SRC_ROY_LOGIN` - optional - auth login for roy (if you use private materials for FAQ)
    - `SRC_ROY_PASSWORD` - optional
    - `LANG` - default="english" - language of chat answers (use english language for set language name)
    - `DEBUG` - default=False - just for runtime logs

that is it
