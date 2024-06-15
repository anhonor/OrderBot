import json

settings = json.load(open('./settings.json', 'r'))
errors = {
    'ERROR_OCCURED': 'An error occurred responding to your command. Please retry, and if the issue persists, contact support.',
    'ERROR_OCCURED_SUPPORT': 'An error occurred responding to your command. Please retry, and if the issue persists, contact support. (@{})'.format(settings['support_handle']),
}
