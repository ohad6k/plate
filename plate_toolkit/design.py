"""The free extension surface the runtime loads on top of the single-file server.

`mcp/plate.py` keeps seven tools of its own and asks this module for the rest.
In the Starter that is three: activation status, local image inspection and
local browser capture. Together they are the ten free Plate tools.

Plate Pro adds design systems, complete worked implementations, one-call project
assembly, the project contract and review record, Studio and the online library.
None of that source is in this repository. The Pro tool names appear below only
so an older client that calls one by name gets a useful message instead of an
ImportError, and they are never advertised in tools/list.
"""

UPGRADE_URL = 'https://plate-pro-nu.vercel.app/'

PRO_TOOLS = {
    'plate_system': 'reusable Pro design systems',
    'plate_template': 'complete Pro implementations with their previews',
    'plate_create_project': 'one-call project assembly from a Pro implementation',
    'plate_start': 'Pro project contracts',
    'plate_review': 'the Pro before/after review record',
    'plate_studio': 'the local Pro Studio workbench',
    'plate_cloud_library': 'the online Plate library',
    'plate_cloud_projects': 'private saved briefs',
}

STRING = {'type': 'string'}


def tool_definitions():
    """The free half of the tool list. Pro definitions are not built here."""
    return [
        {'name': 'plate_license',
         'description': 'Report local Plate activation status without exposing the key. '
                        'The Starter reports an unactivated install honestly.',
         'inputSchema': {'type': 'object', 'properties': {}, 'required': []}},
        {'name': 'plate_inspect',
         'description': 'Return an actual local screenshot as an MCP image block for the agent to '
                        'visually inspect, plus objective image facts.',
         'inputSchema': {'type': 'object', 'properties': {'path': dict(STRING)}, 'required': ['path']}},
        {'name': 'plate_capture',
         'description': 'Capture a running local website with an isolated Chromium browser. Returns '
                        'an actual MCP image plus overflow, image loading and page error evidence. '
                        'No authenticated sessions.',
         'inputSchema': {'type': 'object', 'properties': {
             'url': dict(STRING),
             'width': {'type': 'integer', 'minimum': 320, 'maximum': 2560},
             'height': {'type': 'integer', 'minimum': 320, 'maximum': 1800},
             'wait_ms': {'type': 'integer', 'minimum': 0, 'maximum': 10000},
             'reduced_motion': {'type': 'boolean',
                                'description': 'Ask the page for reduced motion. Default true. Pass false to '
                                               'capture an animated state; a still frame still says nothing '
                                               'about timing, easing or how the motion reads over time.'}},
             'required': ['url']}},
    ]


def license_status():
    """Activation status with Starter-appropriate next steps. Never returns a key."""
    from . import licensing
    result = licensing.status()
    if result.get('status') != 'active':
        result['next'] = ('This is the free Plate Starter. Pro activation, Studio and the Pro tools '
                          'ship with the Plate Pro distribution: ' + UPGRADE_URL)
    result['distribution'] = 'starter'
    return result


def call(name, args):
    """Dispatch the free extension tools; explain the paid ones instead of failing oddly."""
    if name == 'plate_license':
        return license_status()
    if name in ('plate_inspect', 'plate_capture'):
        from . import vision
        return (vision.inspect_image if name == 'plate_inspect' else vision.capture)(**args)
    if name in PRO_TOOLS:
        raise ValueError('{0} is a Plate Pro tool ({1}) and is not part of the free Starter. '
                         'Pro is a separate distribution: {2}'.format(name, PRO_TOOLS[name], UPGRADE_URL))
    raise ValueError('unknown tool: ' + str(name))
