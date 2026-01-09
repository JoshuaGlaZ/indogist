import base64
import os
import json
import re
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils.safestring import mark_safe
from config import settings
from ml.summarization.utils import add_to_indosum_dataset

from .models import Summary
from .forms import SummaryForm

from ml.summarization.hybrid import predict_and_summarize
from ml.summarization.traditional import summarize_traditional

def home(request):
    """Home page logic."""
    context = {}
    if request.user.is_authenticated:
        recent_summaries = Summary.objects.filter(
            user=request.user).order_by('-created_at')[:5]
        context['recent_summaries'] = recent_summaries
    return render(request, 'summarizer/home.html', context)

def _parse_uploaded_file(uploaded_file):
    """Helper: Parse uploaded text file with template format."""
    try:
        content = uploaded_file.read().decode('utf-8')
        title_match = re.search(r'^TITLE=(.*)', content, re.MULTILINE)
        text_match = re.search(r'^TEXT=(.*)', content, re.MULTILINE | re.DOTALL)

        if title_match and text_match:
            return title_match.group(1).strip(), text_match.group(1).strip()
        raise ValueError("File format invalid. Please use the official template.")
    except UnicodeDecodeError:
        raise ValueError("Unable to read file. Please ensure it's a valid UTF-8 text file.")

def summarize_view(request):
    """Main summarization view with hybrid error handling"""
    form = SummaryForm()

    if request.method == 'POST':
        post_data = request.POST.copy()
        
        # Handle File Upload
        if 'file' in request.FILES and request.FILES['file']:
            try:
                title, text = _parse_uploaded_file(request.FILES['file'])
                post_data.update({'title': title, 'original_text': text})
            except ValueError as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': str(e)}, status=400)
                messages.error(request, str(e))
                return render(request, 'summarizer/summarize.html', {'form': form})

        form = SummaryForm(post_data, request.FILES)

        # Validation & Processing
        if form.is_valid():
            data = form.cleaned_data
            try:
                # Generate Summary
                if data['method'] == 'hybrid':
                    result = predict_and_summarize(
                        text=data['original_text'],
                        title=data['title'],
                        compression_ratio=data['compression_ratio']
                    )
                    summary_text = result['summary']
                    entities = result['entities']
                else:
                    summary_text = summarize_traditional(
                        text=data['original_text'],
                        title=data['title'],
                        compression_ratio=data['compression_ratio']
                    )
                    entities = []

                # Save (if authenticated)
                summary_id = None
                if request.user.is_authenticated:
                    summary_obj = Summary.objects.create(
                        user=request.user,
                        title=data['title'],
                        original_text=data['original_text'],
                        summary_text=summary_text,
                        compression_ratio=data['compression_ratio'],
                        entities=entities,
                        method=data['method']
                    )
                    summary_id = summary_obj.id

                # JSON Response (for AJAX)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'mode': 'user' if request.user.is_authenticated else 'guest',
                        'summary': summary_text,
                        'entities': entities,
                        'summary_id': summary_id
                    })

                # Standard Response (Fallback)
                messages.success(request, '✓ Summary generated successfully!')
                return render(request, 'summarizer/summarize.html', {
                    'form': form,
                    'result': {'summary': summary_text, 'entities': entities, 'id': summary_id}
                })

            except Exception as e:
                error_msg = f'Failed to generate summary: {str(e)}'
                print(f"[ERROR] summarize_view: {e}")
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': error_msg}, status=500)
                messages.error(request, error_msg)
        else:
            # Form validation failed
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                errors = [f"{field}: {', '.join(errs)}" for field, errs in form.errors.items()]
                return JsonResponse({
                    'success': False, 
                    'error': 'Validation failed: ' + '; '.join(errors)
                }, status=400)
            messages.error(request, 'Please correct the errors below.')

    return render(request, 'summarizer/summarize.html', {'form': form})

@login_required
def summary_detail(request, pk):
    """Detail view for a single summary"""
    summary = get_object_or_404(Summary, pk=pk, user=request.user)

    # Process entities for display
    entities_list = []
    if summary.entities and isinstance(summary.entities, list):
        for entity in summary.entities:
            if isinstance(entity, dict) and 'confidence' in entity:
                entity['confidence_percent'] = f"{entity['confidence'] * 100:.0f}"
                entities_list.append(entity)

    context = {
        'summary': summary,
        'compression_display': f"{summary.compression_ratio * 100} %",
        'entities_list': entities_list,
        'entities_json': mark_safe(json.dumps(entities_list)),
        'actual_compression': summary.actual_compression * 100 if summary.actual_compression else 0,
    }
    return render(request, 'summarizer/summary_detail.html', context)


@login_required
def history(request):
    """View all summaries with search and filtering"""
    search_query = request.GET.get('q', '')
    method_filter = request.GET.get('method', '')
    sort_by = request.GET.get('sort', '-created_at')

    summaries = Summary.objects.filter(user=request.user)

    if search_query:
        summaries = summaries.filter(
            Q(title__icontains=search_query) |
            Q(original_text__icontains=search_query) |
            Q(summary_text__icontains=search_query)
        )

    if method_filter:
        summaries = summaries.filter(method=method_filter)

    if sort_by:
        summaries = summaries.order_by(sort_by)

    paginator = Paginator(summaries, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'method_filter': method_filter,
        'sort_by': sort_by,
    }
    return render(request, 'summarizer/history.html', context)


@login_required
def charts_view(request):
    """Display model metrics from static files"""
    base_path = os.path.join(settings.BASE_DIR, 'ml', 'models', 'ner2_tuningHYPERBAND_FINAL')

    context = {
        'chart_image': None,
        'classification_report': [],
        'experiment_metrics': None,
        'file_error': None
    }

    try:
        img_path = os.path.join(base_path, 'training_history.png')
        if os.path.exists(img_path):
            with open(img_path, "rb") as image_file:
                encoded_string = base64.b64encode(
                    image_file.read()).decode('utf-8')
                context['chart_image'] = f"data:image/png;base64,{encoded_string}"

        report_path = os.path.join(base_path, 'classification_report.txt')
        report_data = []
        if os.path.exists(report_path):
            with open(report_path, 'r') as f:
                lines = f.readlines()
                for line in lines[2:]: 
                    parts = line.split()
                    if not parts: continue

                    if parts[0] == 'accuracy':
                        report_data.append({
                            'label': 'accuracy',
                            'precision': '',
                            'recall': '',
                            'f1': parts[1],
                            'support': parts[2] if len(parts) > 2 else ''
                        })
                    elif len(parts) >= 5:
                        if parts[1] == 'avg':
                            label = f"{parts[0]} {parts[1]}"
                            scores = parts[2:]
                        else:
                            label = parts[0]
                            scores = parts[1:]
                        report_data.append({
                            'label': label,
                            'precision': scores[0],
                            'recall': scores[1],
                            'f1': scores[2],
                            'support': scores[3]
                        })
            context['classification_report'] = report_data

        json_path = os.path.join(base_path, 'experiment_results.json')
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                data = json.load(f)
                config = data.get('config', {})

                context['experiment_metrics'] = {
                    'Architecture': {
                        'Embedding Dim': config.get('embed_dim'),
                        'LSTM Units': config.get('lstm_units'),
                        'Layers': config.get('num_lstm_layers'),
                        'Dropout': config.get('dropout'),
                    },
                    'Training': {
                        'Epochs': config.get('epochs'),
                        'Batch Size': config.get('batch_size'),
                        'Patience': config.get('patience'),
                        'Learning Rate': config.get('learning_rate'),
                    },
                    'Performance': {
                        'Accuracy': f"{data.get('metrics', {}).get('accuracy', 0):.4f}",
                        'Timestamp': data.get('timestamp')[:10]
                    }
                }

    except Exception as e:
        context['file_error'] = str(e)

    return render(request, 'summarizer/charts.html', context)


def comparison_view(request):
    """Compare traditional vs hybrid methods"""
    if request.method == 'POST':
        text = request.POST.get('text', '').strip()
        title = request.POST.get('title', '').strip()
        try:
            compression_ratio = float(request.POST.get('compression_ratio', 0.3))
        except ValueError:
            compression_ratio = 0.3

        if not text or not title:
            error_msg = 'Please provide both title and text'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return render(request, 'summarizer/comparison.html')

        try:
            traditional_summary = summarize_traditional(
                text=text,
                title=title,
                compression_ratio=compression_ratio
            )

            hybrid_result = predict_and_summarize(
                text=text,
                title=title,
                compression_ratio=compression_ratio
            )

            response_data = {
                'success': True,
                'traditional': traditional_summary,
                'hybrid': hybrid_result['summary'],
                'traditional_words': len(traditional_summary.split()),
                'hybrid_words': len(hybrid_result['summary'].split()),
                'original_words': len(text.split())
            }

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(response_data)

            return render(request, 'summarizer/comparison.html', response_data)

        except Exception as e:
            error_msg = f'Comparison failed: {str(e)}'
            print(f"[ERROR] comparison_view: {e}")
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg}, status=500)
            messages.error(request, error_msg)

    return render(request, 'summarizer/comparison.html')


@login_required
@require_http_methods(["POST"])
def add_to_dataset(request, pk):
    """Add summary to training dataset"""
    summary = get_object_or_404(Summary, pk=pk, user=request.user)

    if summary.added_to_dataset:
        return JsonResponse({
            'success': False,
            'error': 'This summary has already been added to the dataset'
        }, status=400)

    try:
        add_to_indosum_dataset(
            title=summary.title,
            text=summary.original_text,
            summary=summary.summary_text,
            user=request.user.username
        )

        summary.added_to_dataset = True
        summary.save()

        return JsonResponse({
            'success': True,
            'message': 'Successfully added to dataset!'
        })

    except Exception as e:
        print(f"ERROR in add_to_dataset: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def export_summary(request, pk):
    """Export summary as text file"""
    summary = get_object_or_404(Summary, pk=pk, user=request.user)

    response = HttpResponse(content_type='text/plain; charset=utf-8')
    filename = f'summary_{summary.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    content = f"""TITLE: {summary.title}

SUMMARY:
{summary.summary_text}

ORIGINAL TEXT:
{summary.original_text}
"""
    response.write(content)
    return response


def download_template(request):
    """Download template file for text upload"""
    response = HttpResponse(content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="summarizer_template.txt"'

    template = """IMPORTANT INSTRUCTIONS:
1. Do not remove the 'TITLE=' and 'TEXT=' lines
2. Place your title after 'TITLE='
3. Place your entire text content after 'TEXT='

TITLE=
TEXT=
"""
    response.write(template)
    return response