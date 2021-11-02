from datetime import datetime
from flask import Blueprint, jsonify

from CLIPy import Clip

bp = Blueprint('clipy', __name__, url_prefix='')

clip = Clip()


@bp.route('/')
def index():
    return "The computer is computing!"


@bp.route('/buildings/', methods=['GET'])
def get_building():
    return jsonify(clip.list_buildings())


@bp.route('/rooms/', methods=['GET'])
def get_rooms():
    return jsonify(clip.list_rooms())


@bp.route('/departments/', methods=['GET'])
def get_departments():
    return jsonify(clip.get_departments())


@bp.route('/courses/', methods=['GET'])
def get_courses():
    return jsonify(clip.list_courses())


@bp.route('/students/', methods=['GET'])
def get_students():
    return jsonify(clip.list_students())


@bp.route('/teachers/', methods=['GET'])
def get_teachers():
    return jsonify(clip.list_teachers())


@bp.route('/student/<int:student_id>', methods=['GET'])
def get_student(student_id):
    return jsonify(clip.get_student(student_id))


@bp.route('/department/<int:department_id>', methods=['GET'])
def get_department(department_id):
    return jsonify(clip.get_department(department_id))


@bp.route('/classes/', methods=['GET'])
def get_classes():
    return jsonify(clip.get_classes())


@bp.route('/class/<int:class_id>', methods=['GET'])
def get_class(class_id):
    return jsonify(clip.get_class(class_id))


@bp.route('/class_inst/<int:instance_id>', methods=['GET'])
def get_class_instance(instance_id):
    return jsonify(clip.get_class_instance(instance_id))


@bp.route('/files/<int:instance_id>', methods=['GET'])
def get_files(instance_id):
    return jsonify(clip.get_class_instance_files(instance_id))


@bp.route('/events/<int:instance_id>', methods=['GET'])
def get_events(instance_id):
    return jsonify(clip.get_events(instance_id))


@bp.route('/shift/<int:shift_id>', methods=['GET'])
def get_shift(shift_id):
    return jsonify(clip.get_shift(shift_id))


@bp.route('/shift_inst/<int:shift_inst_id>', methods=['GET'])
def get_shift_instance(shift_inst_id):
    return jsonify(clip.get_shift_instance(shift_inst_id))


@bp.route('/enrollment/<int:enrollment_id>', methods=['GET'])
def get_enrollment(enrollment_id):
    return jsonify(clip.get_enrollment(enrollment_id))


@bp.route('/evaluation/<int:evaluation_id>', methods=['GET'])
def get_evaluation(evaluation_id):
    return jsonify(clip.get_evaluation(evaluation_id))


@bp.route('/library_occupation/<string:day>', methods=['GET'])
def get_library_info(day):
    date = datetime.strptime(day, "%Y-%m-%d").date()
    return jsonify({
        'individual': clip.fetch_library_individual_room_availability(date),
        'group': clip.fetch_library_group_room_availability(date)
    })


@bp.route('/update/courses/', methods=['GET'])
def update_courses():
    clip.update_courses()
    return "Success"


@bp.route('/update/rooms/', methods=['GET'])
def update_rooms():
    clip.update_rooms()
    return "Success"


@bp.route('/update/classes/', methods=['GET'])
def update_classes():
    clip.update_classes()
    return "Success"


@bp.route('/update/teachers/', methods=['GET'], defaults={'department_id': None})
@bp.route('/update/teachers/<int:department_id>', methods=['GET'])
def update_teachers(department_id):
    clip.update_teachers(department_id)
    return "Success"


@bp.route('/update/admissions/', methods=['GET'])
def update_admissions():
    clip.update_admissions()
    return "Success"


@bp.route('/update/class_info/<int:class_instance_id>', methods=['GET'])
def update_class_info(class_instance_id):
    clip.update_class_info(class_instance_id)
    return "Success"


@bp.route('/update/class_enrollments/<int:class_instance_id>', methods=['GET'])
def update_class_enrollments(class_instance_id):
    clip.update_class_enrollments(class_instance_id)
    return "Success"


@bp.route('/update/shifts/<int:class_instance_id>', methods=['GET'])
def update_shifts(class_instance_id):
    clip.update_class_shifts(class_instance_id)
    return "Success"


@bp.route('/update/events/<int:class_instance_id>', methods=['GET'])
def update_events(class_instance_id):
    clip.update_class_events(class_instance_id)
    return "Success"


@bp.route('/update/class_files/<int:class_instance_id>', methods=['GET'])
def update_class_files(class_instance_id):
    clip.update_class_files(class_instance_id)
    return "Success"


@bp.route('/update/class_grades/<int:class_instance_id>', methods=['GET'])
def update_class_grades(class_instance_id):
    clip.update_class_grades(class_instance_id)
    return "Success"
