from worker import AnalyserWorker
from jinja2 import Template
from openai import OpenAI, OpenAIError
import logging
import traceback
import json
import time

logging.getLogger().setLevel(logging.INFO)

# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """
In addition to the user's request, you will be provided with a list of functions that you can call if
their criteria is met. You must ALWAYS call "set_response" to provide your response to the user. 

YOU MUST ALWAYS CALL debug_reasoning.
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
                    "name": "set_response",
                    "description": "Provide your response to the user using this function. This should be a response identical to how you'd respond in a context without function calling.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "response": {
                                "type": "string",
                                "description": "Provide your response to the user's prompt in this argument."
                            }
                        },
                        "required": [
                            "response"
                        ],
                        "additionalProperties": False
                    },
                    "strict": True
                }
            },
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
                    "name": "discard_result",
                    "description": "Sets whether your response should be discarded. This should ONLY be called IF the user's request has specified criteria under which this should be called. For example, the user may provide you a message to analyse, and ask that you NOT save the result IF the message contains personal information. In that scenario, you would call discard_result ONLY if the message contained personal information, just as the user requested.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {
                                "type": "string",
                                "description": "Your reasoning on why you are discarding this result. It better be good."
                            }
                        },
                        "required": [
                            "reason"
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
            {
               "type": "function",
                "function": {
                    "name": "debug_reasoning",
                    "description": "Call this function to provide your reasoning for why you called save_result() the way you did. YOU MUST ALWAYS CALL THIS FUNCTION AND PROVIDE YOUR REASONING.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {
                                "type": "string",
                                "description": "Explain why you called save_result() in the way you did."
                            }
                        },
                        "required": [
                            "reason"
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
            logging.info("Sending API request..")
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
            for call in calls:
                args = json.loads(call.function.arguments)
                if call.function.name == 'set_response':
                    self.response = args['response']
                if call.function.name == 'set_title':
                    self.title = args['title']
                if call.function.name == 'discard_result':
                    logging.info(f"GPT is discarding because: {args['reason']}")
                    self.save_flag = False
                if call.function.name == 'set_importance':
                    self.importance = args['importance']
                if call.function.name == 'debug_reasoning':
                    logging.info(f"GPT reasoning is: {args['reason']}")

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
        start_time = time.time()
        logging.info("----------------------------------------------------")
        logging.info("                    TASK START                      ")
        logging.info("----------------------------------------------------")
        logging.info(f"Data:    {record.uuid}")
        logging.info(f"Task:    {task.name}")
        logging.info(f"Trigger events: {trigger.events}")
        #logging.info(f"Trigger parameters: {trigger.parameters}")
        logging.info("")

        # These default options can be changed by GPT through function calls
        self.title = f"GPT Analysis - {task.name}"
        self.importance = 'normal'
        self.save_flag = True
        self.response = None

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
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        # Prompt 1 - Get textual response
        completion = self._create_completion(messages, self.tools)
        if not completion:
            logging.error("Text API request failed, terminating!")
            return

        # Process the function calls to get the response and other attributes
        self._handle_function_calls(completion.choices[0].message.tool_calls)

        payload = {
            'result': self.response,
        }

        # Save some metadata to the database about the GPT calls
        metadata = {
            'completion_tokens': completion.usage.completion_tokens,
            'prompt_tokens': completion.usage.prompt_tokens,
            'total_tokens': completion.usage.total_tokens,
            'model': completion.model,
            'id': completion.id
        }

        if self.save_flag:
            logging.info(f"Saving result with title: '{self.title}'")
            self.save_result(self.title,
                             payload,
                             record,
                             task,
                             importance=self.importance,
                             display=display)

        end_time = time.time()
        logging.info("----------------------------------------------------")
        logging.info(f"Task took {end_time - start_time:.2f}s")
        logging.info("----------------------------------------------------")
        logging.info("")
        logging.info("")

# --------------------------------------------------------------------------- #

def main():
    w = GPTAnalyser()
    w.start()

# --------------------------------------------------------------------------- #

if __name__ == '__main__':
    main()
