import logging

from accounts.models import UserRole
from asgiref.sync import async_to_sync
from core.utils import generate_fake_name
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.timezone import now
from django.views.decorators.http import require_GET

from .models import Message
from .models import Simulation

logger = logging.getLogger(__name__)


@login_required
def index(request):
    simulations = (
        Simulation.objects.filter(user=request.user)
        if request.user.is_authenticated
        else Simulation.objects.none()
    )
    search_query = request.GET.get("q", "").strip()
    search_messages = request.GET.get("search_messages") == "1"

    if search_query:
        if search_messages:
            simulations = simulations.filter(
                message__content__icontains=search_query
            ).distinct()
        else:
            simulations = simulations.filter(description__icontains=search_query)

    simulations = simulations.order_by("-start_timestamp")
    paginator = Paginator(simulations, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    template = (
        "ChatLab/partials/simulation_history.html"
        if request.htmx
        else "ChatLab/index.html"
    )
    return render(
        request,
        template,
        {
            "simulations": page_obj,
            "search_query": search_query,
            "search_messages": search_messages,
        },
    )


@login_required
def create_simulation(request):
    simulation = Simulation.objects.create(
        user=request.user,
        sim_patient_full_name=generate_fake_name(),
        start_timestamp=now()
    )

    User = get_user_model()
    system_user, _ = User.objects.get_or_create(
        username="System",
        role=UserRole.objects.get_or_create(title="System")[0],
        defaults={"first_name": "System", "is_active": False, },
    )

    # Generate initial scenario and first SIM message in background
    import threading
    from SimManAI.async_client import AsyncOpenAIChatService
    from channels.layers import get_channel_layer

    ai = AsyncOpenAIChatService()

    def start_initial_response(sim):
        logger.debug(
            f"[ChatLab] requesting initial SimMessage for Sim#{sim.id}"
        )
        try:
            # Send initial prompt to OpenAI, generate the initial SimMessage, and create the Message
            sim_responses = async_to_sync(ai.generate_patient_initial)(sim, False)

            # Get channel layer and send the initial SimMessage to the group
            channel_layer = get_channel_layer()
            for message in sim_responses:
                async_to_sync(channel_layer.group_send)(
                    f"simulation_{sim.id}",  # Group name based on simulation ID
                    {
                        "type": "chat_message",
                        "content": message.content,
                        "display_name": sim.sim_patient_full_name,
                    },
                )
        except Exception as e:
            logger.exception(
                f"Failed to generate initial SimMessage for Sim#{sim.id}: {e}"
            )

    threading.Thread(
        target=start_initial_response, args=(simulation,), daemon=True
    ).start()

    return redirect("ChatLab:run_simulation", simulation_id=simulation.id)


@login_required
def run_simulation(request, simulation_id):
    simulation = get_object_or_404(Simulation, id=simulation_id)
    metadata = simulation.metadata.exclude(attribute="feedback")
    feedback = simulation.metadata.filter(attribute="feedback")

    if simulation.user != request.user:
        return HttpResponseForbidden(
            "You do not have permission to view this simulation."
        )

    context = {
        "simulation": simulation,
        "metadata": metadata,
        "sim_start_unix": int(simulation.start_timestamp.timestamp() * 1000),
        "simulation_locked": simulation.is_complete,
        "feedback": feedback,
    }

    return render(request, "ChatLab/simulation.html", context)


@require_GET
def refresh_metadata(request, simulation_id):
    simulation = get_object_or_404(Simulation, id=simulation_id)

    if request.GET.get("force") != "1":
        new_checksum = simulation.calculate_metadata_checksum()
        if new_checksum == simulation.metadata_checksum:
            return JsonResponse({"changed": False})
        simulation.metadata_checksum = new_checksum
        simulation.save(update_fields=["metadata_checksum"])

    context = {
        "simulation": simulation,
        "metadata": simulation.metadata.all(),
    }
    logger.debug(
        f"[Sim#{simulation.pk}] refreshed metadata: {context.get('metadata')}"
    )
    return render(request, "ChatLab/partials/_metadata_inner.html", context)

@require_GET
def refresh_messages(request, simulation_id):
    messages = Message.objects.filter(simulation_id=simulation_id).order_by(
        "-timestamp"
    )[:5]
    messages = reversed(messages)  # Show oldest at top
    return render(request, "ChatLab/partials/messages.html", {"messages": messages})


@require_GET
def load_older_messages(request, simulation_id):
    before_id = request.GET.get("before")
    try:
        before_message = Message.objects.get(id=before_id)
    except Message.DoesNotExist:
        return JsonResponse({"error": "Message not found."}, status=404)

    messages = Message.objects.filter(
        simulation_id=simulation_id, timestamp__lt=before_message.timestamp
    ).order_by("-timestamp")[:5]
    messages = reversed(messages)
    return render(request, "ChatLab/partials/messages.html", {"messages": messages})


from django.views.decorators.http import require_POST


@require_POST
@login_required
def end_simulation(request, simulation_id):
    simulation = get_object_or_404(Simulation, id=simulation_id, user=request.user)
    if not simulation.end_timestamp:
        simulation.end()
    return redirect("ChatLab:run_simulation", simulation_id=simulation.id)
