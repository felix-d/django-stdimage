# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import resource
import sys
import traceback
from multiprocessing import Pool, cpu_count

import progressbar
from django.core.management import BaseCommand
from django.db.models import get_model

from stdimage.utils import render_variations

BAR = None


class MemoryUsageWidget(progressbar.widgets.Widget):
    def update(self, pbar):
        return 'RAM: {0:10.1f} MB'.format(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        )


class Command(BaseCommand):
    help = 'Renders all variations of a StdImageField.'
    args = '<app.model.field app.model.field>'

    def add_arguments(self, parser):
        parser.add_argument('--replace',
                            action='store_true',
                            dest='replace',
                            default=False,
                            help='Replace existing files.')

    def handle(self, *args, **options):
        replace = options.get('replace')
        for route in args:
            app_label, model_name, field_name = route.rsplit('.')
            model_class = get_model(app_label, model_name)
            field = model_class._meta.get_field(field_name)

            queryset = model_class._default_manager \
                .exclude(**{'%s__isnull' % field_name: True}) \
                .exclude(**{field_name: ''})
            images = queryset.values_list(field_name, flat=True)

            pool = Pool(
                initializer=init_progressbar,
                initargs=[queryset.count()]
            )
            args = [
                dict(
                    file_name=file_name,
                    variations=field.variations,
                    replace=replace,
                )
                for file_name in images
            ]
            pool.map(render_field_variations, args)
            pool.apply(finish_progressbar)
            pool.close()
            pool.join()


def init_progressbar(count):
    global BAR
    BAR = progressbar.ProgressBar(maxval=count, widgets=(
        progressbar.RotatingMarker(),
        ' | ', MemoryUsageWidget(),
        ' | CPUs: {}'.format(cpu_count()),
        ' | ', progressbar.AdaptiveETA(),
        ' | ', progressbar.Percentage(),
        ' ', progressbar.Bar(),
    ))


def finish_progressbar():
    global BAR
    BAR.finish()


def render_field_variations(kwargs):
    try:
        global BAR
        render_variations(**kwargs)
        BAR += 1
    except:
        raise Exception("".join(traceback.format_exception(*sys.exc_info())))
