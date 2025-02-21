# Silvermoon

**Silvermoon** is an event-driven data collection and analysis framework, primarily designed for the automated collection and processing of open source intelligence (OSINT).

![](https://github.com/joestanding/silvermoon-private/blob/main/images/results.png?raw=true)

I developed Silvermoon to replace a varying set of individual collection and analysis scripts, all of which saved data in different formats and were not interoperable. I wanted to build a system which had a common definition of **Collectors** and **Analysers**, from which task-specific implementations could derive.

An event-driven approach allows analysers to trigger based on events raised by other components, such as new data collected by a collector, or an analysis result saved by a different analyser. This approach allows for chaining of multiple workers to produce different results. For example, a translation worker may act upon new data collected by a foreign-targeted Telegram collector, and multiple different analysis workers may act upon the translation result.

## Stack
- **Python** for all scripts
- **Flask** as the web interface framework
- **MongoDB** for storage of collected data and analysis results
- **Redis** for the shared event queue amongst collectors and analysers

## Architecture
Collectors are responsible for the retrieval of data, such as messages posted in public Telegram channels, or public Tweets. Analysers are responsible for the analysis of data retrieved by the Collectors. Analysers can perform any task on saved data, such as the translation from one language to another, or using the stored data within an LLM prompt to generate an analytical product.

Collectors and analysers communicate with one another using a Redis Pub/Sub queue. Collectors raise a `NEW_DATA` event with a reference to the collected data in the database, which can then be listened for and acted upon by analysers.

Analysers are configured through the use of **Tasks**, which define the criteria and events on which they should act. A task defines a high-level goal, such as "Summarise Geopolitical Events" or "Detect Leaked Credentials".

Each **Task** can have multiple **Triggers**. An individual Trigger defines the event the task can fire upon, the source worker of the event, and what data should be passed to the analysis worker. This allows a single task, for example "Translate Ukrainian to English", to act differently upon events from different workers, but do so under one unifying task.

For example, a task that passes information to an LLM for processing may want to pass different attributes of the data depending on its source. If acting upon data from Telegram, it may want to pass `payload.message_text`. If acting on data from Twitter, it may have to pass `payload.tweet_text`. Perhaps if certain sources are expected to have lower quality information, they may want to use a cheaper LLM model, and pass `gpt-4o-mini` as the `model` parameter for that source instead of a more expensive option.

## Example Uses
I use Silvermoon extensively for collecting information from public sources such as Telegram and Twitter, which can then be passed into an LLM such as OpenAI's GPT to produce analysis and reporting on topics in which I have interest. For example, Telegram can be a great source of information from the frontlines of conflicts such as the Russia-Ukraine war, however the amount of messages can be high, and if you can't read Ukrainian or Russian it isn't going to be of much immediate use to you.

Silvermoon can allow you to collect information from those sources directly, then pass them in to an LLM for report generation, allowing foreign-language content to be translated, analysed, and then ultimately presented to you in a concise and helpful form via the web interface.

It could also be used for automated detection of concerning content spread on public platforms, such as the dissemination of stolen credentials or calls for violent action. The collector can operate continuously, and the analyser can be configured to only raise a report when relevant content has been detected.

## Installation
Silvermoon is run using **Docker**, which keeps things nicely packaged. You'll need Docker and Docker Compose installed, after which you can run it with the simple command:

`$ docker compose up`

By default, the application will be available on its web interface at port 5000. The web interface does **NOT** feature authentication, so if you do intend to use this in a non-private environment, I recommend you proxy it behind an authentication solution.
