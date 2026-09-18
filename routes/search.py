from flask import Blueprint, request, jsonify, render_template, session
from database import q
bp=Blueprint('search',__name__)
@bp.get('/search')
def page():return render_template('search.html')
@bp.get('/api/search')
def search():
    uid=session.get('user_id')
    if not uid:return jsonify(ok=False,message='Debes iniciar sesión.'),401
    term=str(request.args.get('q','')).strip()[:80]
    if not term:return jsonify(ok=True,users=[],posts=[],reports=[],rooms=[])
    like=f'%{term}%'
    users=[dict(r) for r in q("SELECT id,username,names,last_names,profile_photo FROM users WHERE status='approved' AND (username LIKE ? OR names LIKE ? OR last_names LIKE ?) LIMIT 20",(like,like,like))]
    posts=[dict(r) for r in q("SELECT p.id,p.content,p.created_at,u.username FROM posts p JOIN users u ON u.id=p.user_id WHERE p.status='active' AND p.content LIKE ? ORDER BY p.created_at DESC LIMIT 20",(like,))]
    reports=[dict(r) for r in q("SELECT id,public_id,category,description,status FROM reports WHERE description LIKE ? OR category LIKE ? ORDER BY created_at DESC LIMIT 20",(like,like))]
    rooms=[dict(r) for r in q("SELECT r.id,r.name FROM rooms r JOIN room_members m ON m.room_id=r.id WHERE m.user_id=? AND r.status='active' AND r.name LIKE ?",(uid,like))]
    return jsonify(ok=True,users=users,posts=posts,reports=reports,rooms=rooms)
