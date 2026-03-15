from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from extensions import db
from models import Upload, Result
from processing import process, get_choice_options
import pandas as pd
import os, uuid, json

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def dashboard():
    my_uploads = Upload.query.filter_by(user_id=current_user.id).order_by(Upload.uploaded_at.desc()).all()
    shared_uploads = Upload.query.filter_by(is_shared=True).order_by(Upload.uploaded_at.desc()).all()
    my_results = Result.query.filter_by(user_id=current_user.id).order_by(Result.created_at.desc()).limit(5).all()
    return render_template('dashboard.html',
                           my_uploads=my_uploads,
                           shared_uploads=shared_uploads,
                           my_results=my_results)


@main_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file or file.filename == '':
            flash('Please select a CSV file.', 'error')
            return redirect(request.url)
        if not file.filename.lower().endswith('.csv'):
            flash('Only CSV files are accepted.', 'error')
            return redirect(request.url)

        filename = f"{uuid.uuid4().hex}.csv"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            df = pd.read_csv(filepath, encoding='utf-8', encoding_errors='replace')
            row_count = len(df)
            columns = json.dumps(list(df.columns))
        except Exception as e:
            os.remove(filepath)
            flash(f'Could not parse CSV: {e}', 'error')
            return redirect(request.url)

        is_shared = 'is_shared' in request.form and current_user.is_admin()

        upload_rec = Upload(
            filename=filename,
            original_filename=file.filename,
            user_id=current_user.id,
            is_shared=is_shared,
            row_count=row_count,
            columns=columns,
        )
        db.session.add(upload_rec)
        db.session.commit()
        flash(f'"{file.filename}" uploaded — {row_count} rows found.', 'success')
        return redirect(url_for('main.choices', upload_id=upload_rec.id))

    return render_template('upload.html')


@main_bp.route('/uploads')
@login_required
def manage_uploads():
    if current_user.is_admin():
        all_uploads = Upload.query.order_by(Upload.uploaded_at.desc()).all()
    else:
        all_uploads = Upload.query.filter(
            (Upload.user_id == current_user.id) | (Upload.is_shared == True)
        ).order_by(Upload.uploaded_at.desc()).all()
    return render_template('manage_uploads.html', uploads=all_uploads)


@main_bp.route('/uploads/<int:upload_id>/preview')
@login_required
def preview_upload(upload_id):
    upload_rec = _get_accessible_upload(upload_id)
    if not upload_rec:
        flash('Upload not found or access denied.', 'error')
        return redirect(url_for('main.manage_uploads'))
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], upload_rec.filename)
    try:
        df = pd.read_csv(filepath, encoding='utf-8', encoding_errors='replace')
        columns = list(df.columns)
        rows = df.head(50).fillna('').to_dict(orient='records')
        total_rows = len(df)
        dtypes = {col: str(df[col].dtype) for col in columns}
        stats = {}
        for col in df.select_dtypes(include='number').columns:
            stats[col] = {
                'min': round(df[col].min(), 2),
                'max': round(df[col].max(), 2),
                'mean': round(df[col].mean(), 2),
                'nulls': int(df[col].isnull().sum()),
            }
    except Exception as e:
        flash(f'Could not read file: {e}', 'error')
        return redirect(url_for('main.manage_uploads'))
    return render_template('preview_upload.html',
                           upload=upload_rec,
                           columns=columns,
                           rows=rows,
                           total_rows=total_rows,
                           dtypes=dtypes,
                           stats=stats)


@main_bp.route('/choices/<int:upload_id>', methods=['GET', 'POST'])
@login_required
def choices(upload_id):
    upload_rec = _get_accessible_upload(upload_id)
    if not upload_rec:
        flash('Upload not found or access denied.', 'error')
        return redirect(url_for('main.dashboard'))

    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], upload_rec.filename)
    df = pd.read_csv(filepath, encoding='utf-8', encoding_errors='replace')
    choice_defs = get_choice_options(df)

    if request.method == 'POST':
        user_choices = {}
        for c in choice_defs:
            if c['type'] == 'checkbox':
                user_choices[c['name']] = c['name'] in request.form
            else:
                user_choices[c['name']] = request.form.get(c['name'], c.get('default', ''))

        try:
            output = process(df, user_choices)
        except Exception as e:
            flash(f'Processing error: {e}', 'error')
            return redirect(request.url)

        result = Result(
            upload_id=upload_rec.id,
            user_id=current_user.id,
            choices=json.dumps(user_choices),
            output=json.dumps(output),
        )
        db.session.add(result)
        db.session.commit()
        return redirect(url_for('main.results', result_id=result.id))

    return render_template('choices.html', upload=upload_rec, choice_defs=choice_defs)


@main_bp.route('/results/<int:result_id>')
@login_required
def results(result_id):
    result = Result.query.get_or_404(result_id)
    if result.user_id != current_user.id and not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    output = json.loads(result.output)
    choices = json.loads(result.choices)
    return render_template('results.html', result=result, output=output, choices=choices)


@main_bp.route('/uploads/<int:upload_id>/delete', methods=['POST'])
@login_required
def delete_upload(upload_id):
    upload_rec = Upload.query.get_or_404(upload_id)
    if upload_rec.user_id != current_user.id and not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('main.manage_uploads'))
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], upload_rec.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(upload_rec)
    db.session.commit()
    flash('Upload deleted.', 'success')
    return redirect(url_for('main.manage_uploads'))


def _get_accessible_upload(upload_id):
    upload_rec = Upload.query.get(upload_id)
    if not upload_rec:
        return None
    if upload_rec.user_id == current_user.id:
        return upload_rec
    if upload_rec.is_shared:
        return upload_rec
    if current_user.is_admin():
        return upload_rec
    return None
