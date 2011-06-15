import os
import random
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.utils.translation import ugettext as _
from django.http import HttpResponseRedirect
from django.conf import settings
from django.contrib import messages
from django.core.context_processors import csrf

from form_designer.forms import DesignedForm
from form_designer.models import FormDefinition

def _is_valid_file(file_obj):
    # Make sure the file does not have a bad extension
    bad_extensions = getattr(settings, 'FORM_DESIGNER_BAD_EXTENSIONS',
                             ('.exe', '.js', '.vb', '.ico', '.com', '.bat'))
    basename, extension = os.path.splitext(file_obj.name)
    logger.debug('extension, filename: %s, %s' %
        (extension, file_obj.name))
    if extension in bad_extensions:
        logger.debug('Bad filename detected: %s' % file_obj.name)
        return False
    return True

def process_form(request, form_definition, context={}, is_cms_plugin=False):
    success_message = form_definition.success_message or _('Thank you, the data was submitted successfully.')
    error_message = form_definition.error_message or _('The data could not be submitted, please try again.')
    message = None
    form_error = False
    form_success = False
    is_submit = False
    # If the form has been submitted...
    if request.method == 'POST' and request.POST.get(form_definition.submit_flag_name):
        form = DesignedForm(form_definition, None, request.POST, request.FILES)
        is_submit = True
    if request.method == 'GET' and request.GET.get(form_definition.submit_flag_name):
        form = DesignedForm(form_definition, None, request.GET, request.FILES)
        is_submit = True

    if is_submit:
        if form.is_valid():
            # Handle file uploads
            files = []
            if hasattr(request, 'FILES'):
                for file_key in request.FILES:
                    file_obj = request.FILES[file_key]

                    # Check if its a valid filename, if not, skip this file
                    is_valid_file = _is_valid_file(file_obj)
                    if not is_valid_file:
                        continue

                    file_name = '%s.%s_%s' % (
                        datetime.now().strftime('%Y%m%d'),
                        random.randrange(0, 10000),
                        file_obj.name,
                    )
                    if not os.path.exists(os.path.join(settings.MEDIA_ROOT, 'form_uploads')):
                        os.mkdir(os.path.join(settings.MEDIA_ROOT, 'form_uploads'))
                        logger.debug('Created form uploads directory: %s ' %
                            os.path.join(settings.MEDIA_ROOT, 'form_uploads'))
                    destination = open(os.path.join(settings.MEDIA_ROOT, 'form_uploads', file_name), 'wb+')
                    logger.debug('File upload disk destination: %s ' % destination)
                    for chunk in file_obj.chunks():
                        destination.write(chunk)
                    destination.close()
                    form.cleaned_data[file_key] = os.path.join(settings.MEDIA_URL, 'form_uploads', file_name)
                    files.append(os.path.join(settings.MEDIA_ROOT, 'form_uploads', file_name))

            logger.debug('Files to attach: %s' % files)

            # Successful submission
            messages.success(request, success_message)
            message = success_message
            form_success = True
            if form_definition.log_data:
                form_definition.log(form)
            if form_definition.mail_to:
                form_definition.send_mail(form, files)
            if form_definition.success_redirect and not is_cms_plugin:
                # TODO Redirection does not work for cms plugin
                return HttpResponseRedirect(form_definition.action or '?')
            if form_definition.success_clear:
                form = DesignedForm(form_definition) # clear form
        else:
            form_error = True
            messages.error(request, error_message)
            message = error_message
    else:
        if form_definition.allow_get_initial:
            form = DesignedForm(form_definition, initial_data=request.GET)
        else:
            form = DesignedForm(form_definition)

    context.update({
        'message': message,
        'form_error': form_error,
        'form_success': form_success,
        'form': form,
        'form_definition': form_definition
    })
    context.update(csrf(request))
    return context

def detail(request, object_name):
    form_definition = get_object_or_404(FormDefinition, name=object_name)
    result = process_form(request, form_definition)
    if isinstance(result, HttpResponseRedirect):
        return result
    result.update({
        'form_template': form_definition.form_template_name or settings.DEFAULT_FORM_TEMPLATE
    })
    return render_to_response('html/formdefinition/detail.html', result,
        context_instance=RequestContext(request))
