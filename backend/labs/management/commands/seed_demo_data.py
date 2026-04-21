"""Comando para poblar datos de demostración en el usuario admin."""
import datetime
import io
import math

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from labs.models import AnalysisReport, Biomarker, BiomarkerResult, BodyCompositionReport, ECGReport
from labs.phenoage import update_report_phenoage


# (loinc_code, valor_report1, valor_report2)
# report1 = hace ~1 año — valores saludables  → PhenoAge < edad cronológica
# report2 = reciente    — valores alterados   → PhenoAge > edad cronológica
#
# Biomarcadores para PhenoAge (Levine 2018): ALB, CREA, GLU, PCR, VCM, RDW, FA, WBC, LYMPH
DEMO_VALUES = [
    # ── HEMATOLOGÍA ────────────────────────────────────────────────────────────
    # Leucocitos        normal 4.5–11.0 10³/μL   [PhenoAge: WBC]
    ('6690-2',   6.5,   11.5),   # normal → ALTO
    # Eritrocitos       normal 4.5–5.9 10⁶/μL
    ('789-8',    5.1,    4.6),   # normal → normal
    # Hemoglobina       normal 13.5–17.5 g/dL
    ('718-7',   15.2,   11.8),   # normal → BAJO
    # Hematocrito       normal 41–53 %
    ('4544-3',  45.5,   38.0),   # normal → límite bajo
    # VCM               normal 80–100 fL          [PhenoAge: MCV]
    ('787-2',   88.0,   93.0),   # normal → normal-alto
    # RDW               normal 11.5–14.5 %        [PhenoAge: RDW]
    ('788-0',   12.0,   14.8),   # normal → límite ALTO
    # Plaquetas         normal 150–400 10³/μL
    ('777-3',  215.0,  125.0),   # normal → BAJO
    # Neutrófilos       normal 1.8–7.7 10³/μL
    ('751-8',    3.5,    8.8),   # normal → ALTO
    # Linfocitos        normal 1.0–4.8 10³/μL     [PhenoAge: LYMPH/WBC × 100]
    ('731-0',    2.5,    1.1),   # 38 % → 9.6 %   (linfopenia relativa)
    # ── BIOQUÍMICA ─────────────────────────────────────────────────────────────
    # Glucosa           normal 70–100 mg/dL        [PhenoAge: GLU]
    ('2345-7',  88.0,  112.0),   # normal → prediabetes
    # HbA1c             normal 4.0–6.0 %
    ('4548-4',   5.1,    6.4),   # normal → límite alto
    # Creatinina        normal 0.7–1.2 mg/dL       [PhenoAge: CREA]
    ('2160-0',   0.90,   1.48),  # normal → ALTO
    # Albúmina          normal 3.5–5.0 g/dL        [PhenoAge: ALB]
    ('1751-7',   4.8,    4.0),   # alto-normal → normal-bajo
    # Fosfatasa Alc.    normal 40–130 U/L           [PhenoAge: ALP]
    ('6768-6',  68.0,  128.0),   # normal → límite
    # AST               normal 10–40 U/L
    ('1920-8',  20.0,   52.0),   # normal → ALTO
    # ALT               normal 10–45 U/L
    ('1742-6',  25.0,   88.0),   # normal → ALTO
    # GGT               normal 9–48 U/L
    ('2324-2',  28.0,   95.0),   # normal → ALTO
    # ── LÍPIDOS ────────────────────────────────────────────────────────────────
    # Colesterol total  normal <200 mg/dL
    ('2093-3', 175.0,  232.0),   # normal → ALTO
    # HDL               normal >40 mg/dL
    ('2085-9',  58.0,   32.0),   # normal → BAJO
    # LDL               normal <130 mg/dL
    ('2089-1',  95.0,  165.0),   # normal → ALTO
    # Triglicéridos     normal <150 mg/dL
    ('2571-8', 105.0,  290.0),   # normal → ALTO
    # ── TIROIDES ───────────────────────────────────────────────────────────────
    ('3016-3',   1.9,    6.5),   # normal → ALTO (hipotiroidismo subclínico)
    # ── HIERRO ─────────────────────────────────────────────────────────────────
    ('2276-4', 155.0,   16.0),   # Ferritina: normal → BAJA
    ('2498-4', 105.0,   38.0),   # Hierro sérico: normal → BAJO
    # ── INFLAMACIÓN ────────────────────────────────────────────────────────────
    # PCR               normal <5 mg/L              [PhenoAge: CRP]
    ('1988-5',   0.5,   12.0),   # muy baja → ALTA
    # ── VITAMINAS ──────────────────────────────────────────────────────────────
    ('1989-3',  45.0,   12.0),   # Vitamina D: normal → BAJO
    ('2132-9', 420.0,  145.0),   # Vitamina B12: normal → BAJO
]

REPORT_1 = {
    'name': 'Reconocimiento laboral 2025',
    'date': datetime.date(2025, 3, 15),
    'lab_name': 'Laboratorio Clínico Central',
    'notes': 'Analítica anual de empresa. Resultados excelentes.',
}

REPORT_2 = {
    'name': 'Analítica de control',
    'date': datetime.date(2026, 2, 10),
    'lab_name': 'Clínica San Marcos',
    'notes': 'Revisión por cansancio persistente y mareos. Varios valores alterados.',
}

# (name, date, weight, height, body_fat_pct, visceral_fat, muscle_mass, water_pct, protein_pct, bone_mass, notes)
BODY_REPORTS = [
    {
        'name': 'Báscula — marzo 2025',
        'date': datetime.date(2025, 3, 10),
        'notes': 'Medición en ayunas, antes del reconocimiento.',
        'weight': '78.4',
        'height': '178.0',
        'body_fat_pct': '16.2',
        'visceral_fat': '7.0',
        'muscle_mass': '61.5',
        'water_pct': '60.8',
        'protein_pct': '18.1',
        'bone_mass': '3.4',
    },
    {
        'name': 'Báscula — febrero 2026',
        'date': datetime.date(2026, 2, 5),
        'notes': 'Tras meses con cansancio. Notable aumento de grasa y pérdida muscular.',
        'weight': '85.1',
        'height': '178.0',
        'body_fat_pct': '24.8',
        'visceral_fat': '12.0',
        'muscle_mass': '55.2',
        'water_pct': '54.3',
        'protein_pct': '16.2',
        'bone_mass': '3.2',
    },
]

ECG_REPORTS = [
    {
        'name': 'ECG — reconocimiento 2025',
        'date': datetime.date(2025, 3, 15),
        'notes': 'Ritmo sinusal normal. Sin hallazgos significativos.',
        'heart_rate': 62,
    },
    {
        'name': 'ECG — control 2026',
        'date': datetime.date(2026, 2, 10),
        'notes': 'Taquicardia sinusal leve. Intervalo PR en límite superior.',
        'heart_rate': 98,
    },
]


def _make_ecg_image(heart_rate: int) -> ContentFile:
    """Genera una imagen PNG sintética con forma de ECG."""
    from PIL import Image, ImageDraw

    width, height = 800, 200
    img = Image.new('RGB', (width, height), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)

    # Línea de base
    baseline = height // 2
    draw.line([(0, baseline), (width, baseline)], fill=(200, 200, 200), width=1)

    # Ciclo PQRST sintético — se repite según heart_rate
    bpm = max(40, min(heart_rate, 200))
    cycle_px = int(width * 60 / bpm)  # píxeles por latido a escala ~10 s

    def ecg_y(x_in_cycle, cx):
        """Devuelve y relativo al baseline para un ciclo PQRST."""
        t = x_in_cycle / cx  # 0..1
        # Onda P
        if 0.05 < t < 0.15:
            return -int(12 * math.sin(math.pi * (t - 0.05) / 0.10))
        # Segmento PR
        if 0.15 <= t < 0.28:
            return 0
        # Complejo QRS
        if 0.28 <= t < 0.30:
            return int(8 * (t - 0.28) / 0.02)    # Q (pequeña)
        if 0.30 <= t < 0.34:
            return -int(60 * (t - 0.30) / 0.04)  # R ascenso
        if 0.34 <= t < 0.38:
            return -60 + int(70 * (t - 0.34) / 0.04)  # R descenso + S
        if 0.38 <= t < 0.40:
            return int(10 * (t - 0.38) / 0.02)   # S recuperación
        # Segmento ST
        if 0.40 <= t < 0.50:
            return 0
        # Onda T
        if 0.50 < t < 0.72:
            return -int(20 * math.sin(math.pi * (t - 0.50) / 0.22))
        return 0

    color = (220, 30, 30)
    points = []
    x = 0
    while x < width:
        x_in_cycle = x % cycle_px
        y = baseline + ecg_y(x_in_cycle, cycle_px)
        points.append((x, y))
        x += 1

    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill=color, width=2)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return ContentFile(buf.getvalue(), name='ecg_demo.png')


class Command(BaseCommand):
    help = 'Carga datos de demostración (analíticas, composición corporal y ECG) para el usuario admin.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Elimina los datos de demo existentes antes de crearlos de nuevo.',
        )

    def handle(self, *args, **options):
        try:
            user = User.objects.get(username='admin')
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(
                'No existe el usuario "admin". Ejecútalo tras crear el superusuario.'
            ))
            return

        # Asegurar perfil con datos médicos básicos
        profile = user.userprofile
        if not profile.biological_sex:
            profile.biological_sex = 'M'
        if not profile.birth_date:
            profile.birth_date = datetime.date(1985, 6, 20)
        profile.save()

        # Construir índice de biomarcadores por loinc_code
        biomarkers = {b.loinc_code: b for b in Biomarker.objects.all()}
        if not biomarkers:
            self.stderr.write(self.style.ERROR(
                'No hay biomarcadores. Ejecuta primero: python manage.py seed_biomarkers'
            ))
            return

        if options['reset']:
            analysis_names = [REPORT_1['name'], REPORT_2['name']]
            body_names = [r['name'] for r in BODY_REPORTS]
            ecg_names = [r['name'] for r in ECG_REPORTS]

            d1, _ = AnalysisReport.objects.filter(user=user, name__in=analysis_names).delete()
            d2, _ = BodyCompositionReport.objects.filter(user=user, name__in=body_names).delete()
            d3, _ = ECGReport.objects.filter(user=user, name__in=ecg_names).delete()
            self.stdout.write(
                f'  Eliminados: {d1} analítica(s), {d2} corporal(es), {d3} ECG(s).'
            )

        # ── Analíticas de sangre ──────────────────────────────────────────────
        self.stdout.write('\n  Analíticas:')
        for report_data, valor_idx in [(REPORT_1, 1), (REPORT_2, 2)]:
            report, created = AnalysisReport.objects.get_or_create(
                user=user,
                name=report_data['name'],
                defaults={
                    'date': report_data['date'],
                    'lab_name': report_data['lab_name'],
                    'notes': report_data['notes'],
                },
            )
            if not created:
                self.stdout.write(f'    — ya existe, omitiendo: {report.name}')
                continue

            for loinc_code, val1, val2 in DEMO_VALUES:
                biomarker = biomarkers.get(loinc_code)
                if biomarker is None:
                    self.stderr.write(f'    ⚠ Biomarcador no encontrado: {loinc_code}')
                    continue
                value = val1 if valor_idx == 1 else val2
                BiomarkerResult.objects.create(report=report, biomarker=biomarker, value=value)

            update_report_phenoage(report)
            self.stdout.write(self.style.SUCCESS(f'    ✓ {report.name} ({report.date})'))

        # ── Composición corporal ──────────────────────────────────────────────
        self.stdout.write('\n  Composición corporal:')
        for data in BODY_REPORTS:
            report, created = BodyCompositionReport.objects.get_or_create(
                user=user,
                name=data['name'],
                defaults={
                    'date': data['date'],
                    'notes': data['notes'],
                    'weight': data['weight'],
                    'height': data['height'],
                    'body_fat_pct': data['body_fat_pct'],
                    'visceral_fat': data['visceral_fat'],
                    'muscle_mass': data['muscle_mass'],
                    'water_pct': data['water_pct'],
                    'protein_pct': data['protein_pct'],
                    'bone_mass': data['bone_mass'],
                },
            )
            if not created:
                self.stdout.write(f'    — ya existe, omitiendo: {report.name}')
                continue
            self.stdout.write(self.style.SUCCESS(f'    ✓ {report.name} ({report.date})'))

        # ── ECG ──────────────────────────────────────────────────────────────
        self.stdout.write('\n  ECG:')
        for data in ECG_REPORTS:
            if ECGReport.objects.filter(user=user, name=data['name']).exists():
                self.stdout.write(f'    — ya existe, omitiendo: {data["name"]}')
                continue
            ecg = ECGReport(
                user=user,
                name=data['name'],
                date=data['date'],
                notes=data['notes'],
                heart_rate=data['heart_rate'],
            )
            ecg.image.save('ecg_demo.png', _make_ecg_image(data['heart_rate']), save=False)
            ecg.save()
            self.stdout.write(self.style.SUCCESS(f'    ✓ {ecg.name} ({ecg.date}) — {data["heart_rate"]} bpm'))

        self.stdout.write(self.style.SUCCESS('\nDemo cargado correctamente.'))
