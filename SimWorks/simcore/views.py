from django.http import HttpResponseNotFound, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.views.decorators.http import require_GET

from core.utils import Formatter
from simcore.models import Simulation
from simcore.tools import get_tool


def download_simulation_transcript(request, simulation_id, format_type="sim_transcript_txt"):
    sim = get_object_or_404(Simulation, id=simulation_id)
    formatter = Formatter(sim.history)
    return formatter.download(format_type=format_type, filename=f"Sim{sim.pk}_transcript")

@require_GET
def refresh_tool(request, tool_name, simulation_id):
    simulation = get_object_or_404(Simulation, id=simulation_id)

    tool_class = get_tool(tool_name)
    if not tool_class:
        return HttpResponseNotFound(f"Tool '{tool_name}' not found.")

    tool_instance = tool_class(simulation)
    tool = tool_instance.to_dict()

    # Built partial template path:
    custom_partial = f"simcore/partials/tools/_{tool_name}.html"

    try:
        # Try to load the custom partial
        get_template(custom_partial)
        template = custom_partial
    except TemplateDoesNotExist:
        # Fallback to generic
        template = "simcore/partials/tools/_generic.html"

    return render(request, template, {"tool": tool})

def tool_checksum(request, tool_name, simulation_id):
    simulation = get_object_or_404(Simulation, id=simulation_id)
    tool_class = get_tool(tool_name)
    if not tool_class:
        return JsonResponse({"error": "Tool not found"}, status=404)

    tool_instance = tool_class(simulation)
    checksum = tool_instance.get_checksum()
    return JsonResponse({"checksum": checksum})