from worker import AnalyserWorker
from jinja2 import Template
from openai import OpenAI, OpenAIError
import logging
import traceback
import json

logging.getLogger().setLevel(logging.INFO)

# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """
In addition to the user's request, you will be provided with a list of functions that you can call if
their criteria is met. The criteria for each function call is included in its 'description' field.
You MUST obey the requirements specified in the 'description' field. Do NOT call the functions if
these requirements are not met. DO call these functions if the requirements ARE met.
"""

# --------------------------------------------------------------------------- #

class GPTAnalyser(AnalyserWorker):


    def __init__(self):
        super().__init__("GPTAnalyser")
        self.register_parameter('model', 'The GPT model to use (e.g. gpt3, gpt4o).')
        self.register_parameter('prompt', 'The prompt to be provided to the model.')
        self.register_config('api_key', 'Your OpenAI API key.')
        self.ai = OpenAI(api_key=self.get_config('api_key'))
        self.title = None
        self.tools = [
            {
               "type": "function",
                "function": {
                    "name": "set_title",
                    "description": "Set the title of the deliverable provided to the user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "The title of the result."
                            }
                        },
                        "required": [
                            "title"
                        ],
                        "additionalProperties": False
                    },
                    "strict": True
                }
            },
            {
               "type": "function",
                "function": {
                    "name": "save_result",
                    "description": "Call to set whether the result should be saved. Invoke this function ONLY if the prompt specifies criteria under which the result should NOT be saved.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "decision": {
                                "type": "boolean",
                                "description": "MUST default to 'true' unless the user's prompt explicitly provides criteria under which this result should not be saved. Only call this function if the result MUST NOT be saved."
                            }
                        },
                        "required": [
                            "decision"
                        ],
                        "additionalProperties": False
                    },
                    "strict": True
                }
            },
            {
               "type": "function",
                "function": {
                    "name": "set_importance",
                    "description": "Set the importance of the result. Invoke this function ONLY if the prompt specifies criteria under which the importance should be set.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "importance": {
                                "type": "string",
                                "enum": ["normal", "high"],
                                "description": "Only call if prompt criteria requests setting of importance under certain conditions."
                            }
                        },
                        "required": [
                            "importance"
                        ],
                        "additionalProperties": False
                    },
                    "strict": True
                }
            },


        ]

    # ----------------------------------------------------------------------- #

    def _create_completion(self, messages, tools=None):
        try:
            logging.info("Sending GPT text request..")
            completion = self.ai.chat.completions.create(
                messages=messages,
                model="gpt-4o-mini",
                tools=tools
            )
        except OpenAIError as err:
            logging.error(f"OpenAI API request failed! Error: {err}")
            self.on_error()
            return None
        except Exception as err:
            logging.error("Unexpected error occurred during OpenAI API call!")
            logging.error(f"Error: {err}")
            self.on_error()
            return None

        return completion

    # ----------------------------------------------------------------------- #

    def _handle_function_calls(self, calls):
        if calls:
            logging.info(f"GPT called {len(calls)} function calls")
            for call in calls:
                logging.info(f"Function called: {call.function.name}")
                args = json.loads(call.function.arguments)
                if call.function.name == 'set_title':
                    logging.info(f"GPT set title to: {args['title']}")
                    self.title = args['title']
                if call.function.name == 'save_result':
                    logging.info(f"GPT wants to save result: {args['decision']}")
                    self.save_flag = args['decision']
                if call.function.name == 'set_importance':
                    logging.info(f"GPT set importance to: {args['importance']}")
                    self.importance = args['importance']

    # ----------------------------------------------------------------------- #

    def start(self):
        for record, task, trigger in self.listen_for_tasks():
            try:
                self.process_task(record, task, trigger)
            except Exception as err:
                logging.error("Unhandled exception occured in process_task()!")
                logging.error(f"Details: {err}")
                self.on_error()

    # ----------------------------------------------------------------------- #

    def process_task(self, record, task, trigger):
        logging.info("")
        logging.info("")
        logging.info(f"--- Processing Analysis Task ---")
        logging.info(f"Data:    {record.uuid}")
        logging.info(f"Task:    {task.name}")
        logging.info(f"Trigger events: {trigger.events}")
        logging.info(f"Trigger parameters: {trigger.parameters}")

        # These default options can be changed by GPT through function calls
        self.title = f"GPT Analysis - {task.name}"
        self.importance = 'normal'
        self.save_flag = True

        if 'parameters' not in trigger or 'prompt' not in trigger['parameters']:
            logging.error("Missing params in trigger OR prompt not in params!")
            return

        # Parse the prompt with Jinja to enable injection of data
        template = Template(trigger['parameters']['prompt'])
        prompt = template.render(payload=record['payload'])

        # Defines how the result will appear in the UI, make dynamic in future
        display = {
            'result': 'markdown',
        }

        # Add the prompt to the GPT conversation
        messages = [
            {"role": "user", "content": prompt},
        ]

        # Prompt 1 - Get textual response
        completion_text = self._create_completion(messages)
        if not completion_text:
            logging.error("Text API request failed, terminating!")
            return

        # Prompt 2 - Get function calls
        completion_calls = self._create_completion(messages, self.tools)
        if not completion_calls:
            logging.error("Calls API request failed, terminating!")
            return

        # Extract the response
        message = completion_text.choices[0].message
        response = completion_text.choices[0].message.content

        logging.info(f"GPT response: {response}")

        # Process any function calls GPT may have invoked
        self._handle_function_calls(completion_calls.choices[0].message.tool_calls)


        payload = {
            'result': response,
        }

        # Save some metadata to the database about the GPT calls
        metadata = {
            'completion_tokens': completion_text.usage.completion_tokens,
            'prompt_tokens': completion_text.usage.prompt_tokens,
            'total_tokens': completion_text.usage.total_tokens,
            'model': completion_text.model,
            'id': completion_text.id
        }

        if self.save_flag:
            logging.info(f"Saving result with title: '{self.title}'")
            self.save_result(self.title,
                             payload,
                             record,
                             task,
                             importance=self.importance,
                             display=display)
        else:
            logging.info("GPT requested result NOT be saved!")

# --------------------------------------------------------------------------- #

def main():
    w = GPTAnalyser()
    w.start()

# --------------------------------------------------------------------------- #

if __name__ == '__main__':
    main()
