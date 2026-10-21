import os, sqlite3, csv, io, re
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, send_file, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

ROOT=os.path.abspath(os.path.dirname(__file__))
DB=os.path.join(ROOT,"lost_found.db")
UPLOAD=os.path.join(ROOT,"static","uploads")
os.makedirs(UPLOAD,exist_ok=True)
app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY","change-this-secret-key")
app.config["MAX_CONTENT_LENGTH"]=5*1024*1024
CATEGORIES=["Electronics","ID Card","Books & Notes","Wallet / Keys","Clothing","Bottle / Lunchbox","Accessories","Other"]
LOCATIONS=["Library","Computer Lab","Classroom","Canteen","Sports Ground","Parking","Office","Auditorium","Other"]
def now(): return datetime.now().isoformat(timespec="seconds")
def db():
    if "db" not in g:
        g.db=sqlite3.connect(DB); g.db.row_factory=sqlite3.Row; g.db.execute("PRAGMA foreign_keys=ON")
    return g.db
@app.teardown_appcontext
def close_db(e=None):
    conn=g.pop("db",None)
    if conn: conn.close()
def init_db():
    c=sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'student',created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,post_type TEXT NOT NULL,title TEXT NOT NULL,category TEXT NOT NULL,description TEXT NOT NULL,location TEXT NOT NULL,item_date TEXT NOT NULL,image_filename TEXT,status TEXT NOT NULL DEFAULT 'open',created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS claims(id INTEGER PRIMARY KEY,item_id INTEGER NOT NULL,claimant_id INTEGER NOT NULL,message TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL,FOREIGN KEY(item_id) REFERENCES items(id),FOREIGN KEY(claimant_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,message TEXT NOT NULL,link TEXT,is_read INTEGER DEFAULT 0,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id));
    """)
    if not c.execute("SELECT id FROM users WHERE email='admin@campus.local'").fetchone():
        c.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",("Campus Admin","admin@campus.local",generate_password_hash("Admin@123"),"admin",now()))
    c.commit(); c.close()
def user():
    if session.get("user_id"): return db().execute("SELECT id,name,email,role FROM users WHERE id=?",(session["user_id"],)).fetchone()
    return None
@app.context_processor
def globals_():
    u=user()
    unread=db().execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0",(u["id"],)).fetchone()[0] if u else 0
    return dict(current_user=u,unread_notifications=unread,categories=CATEGORIES,locations=LOCATIONS)
def login_required(fn):
    @wraps(fn)
    def w(*a,**k):
        if not user(): flash("આ પેજ માટે પહેલાં Login કરો.","warning"); return redirect(url_for("login"))
        return fn(*a,**k)
    return w
def admin_required(fn):
    @wraps(fn)
    def w(*a,**k):
        u=user()
        if not u: return redirect(url_for("login"))
        if u["role"]!="admin": abort(403)
        return fn(*a,**k)
    return w
def notify(uid,msg,link=None):
    db().execute("INSERT INTO notifications(user_id,message,link,created_at) VALUES(?,?,?,?)",(uid,msg,link,now())); db().commit()
def words(s): return set(re.findall(r"[a-z0-9]+",(s or "").lower()))
def score(a,b):
    points=0; why=[]
    if a["category"]==b["category"]: points+=35; why.append("same category")
    overlap=words(a["title"]+" "+a["description"]) & words(b["title"]+" "+b["description"])
    if overlap: points+=min(35,len(overlap)*8); why.append("similar words: "+", ".join(list(overlap)[:4]))
    if a["location"]==b["location"]: points+=20; why.append("same location")
    try:
        days=abs((datetime.strptime(a["item_date"],"%Y-%m-%d")-datetime.strptime(b["item_date"],"%Y-%m-%d")).days)
        if days<=1: points+=10; why.append("dates are close")
        elif days<=7: points+=5; why.append("dates within a week")
    except: pass
    return min(points,100),why
@app.route("/")
def home():
    c=db()
    stats=[c.execute("SELECT COUNT(*) FROM items WHERE post_type='lost' AND status='open'").fetchone()[0],c.execute("SELECT COUNT(*) FROM items WHERE post_type='found' AND status='open'").fetchone()[0],c.execute("SELECT COUNT(*) FROM items WHERE status='resolved'").fetchone()[0],c.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0]]
    items=c.execute("SELECT i.*,u.name poster_name FROM items i JOIN users u ON u.id=i.user_id WHERE i.status='open' ORDER BY i.id DESC LIMIT 6").fetchall()
    return render_template("home.html",stats=stats,items=items)
@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form.get("name","").strip(); email=request.form.get("email","").strip().lower(); pw=request.form.get("password","")
        if not name or not email or len(pw)<8: flash("બધી વિગતો भरो. Password ઓછામાં ઓછો 8 અક્ષરનો હોવો જોઈએ.","danger")
        else:
            try:
                db().execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",(name,email,generate_password_hash(pw),"student",now())); db().commit()
                flash("Account બની ગયું. હવે Login કરો.","success"); return redirect(url_for("login"))
            except sqlite3.IntegrityError: flash("આ email પહેલેથી નોંધાયેલું છે.","danger")
    return render_template("auth.html",mode="register")
@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        row=db().execute("SELECT * FROM users WHERE email=?",(request.form.get("email","").lower().strip(),)).fetchone()
        if row and check_password_hash(row["password_hash"],request.form.get("password","")):
            session.clear(); session["user_id"]=row["id"]; flash("Login સફળ થયું.","success"); return redirect(url_for("dashboard"))
        flash("Email અથવા password ખોટો છે.","danger")
    return render_template("auth.html",mode="login")
@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("home"))
@app.route("/dashboard")
@login_required
def dashboard():
    u=user(); c=db()
    if u["role"]=="admin":
        mine=c.execute("SELECT COUNT(*) FROM items").fetchone()[0]; pending=c.execute("SELECT COUNT(*) FROM claims WHERE status='pending'").fetchone()[0]
        rows=c.execute("SELECT i.*,u.name poster_name FROM items i JOIN users u ON u.id=i.user_id ORDER BY i.id DESC LIMIT 12").fetchall()
    else:
        mine=c.execute("SELECT COUNT(*) FROM items WHERE user_id=?",(u["id"],)).fetchone()[0]; pending=c.execute("SELECT COUNT(*) FROM claims WHERE claimant_id=? AND status='pending'",(u["id"],)).fetchone()[0]
        rows=c.execute("SELECT i.*,u.name poster_name FROM items i JOIN users u ON u.id=i.user_id WHERE i.user_id=? ORDER BY i.id DESC LIMIT 12",(u["id"],)).fetchall()
    stats=[c.execute("SELECT COUNT(*) FROM items WHERE post_type='lost' AND status='open'").fetchone()[0],c.execute("SELECT COUNT(*) FROM items WHERE post_type='found' AND status='open'").fetchone()[0],mine,pending]
    return render_template("dashboard.html",stats=stats,items=rows)
@app.route("/items")
def browse():
    q=request.args.get("q","").strip(); typ=request.args.get("type",""); cat=request.args.get("category",""); loc=request.args.get("location",""); status=request.args.get("status","open")
    sql="SELECT i.*,u.name poster_name FROM items i JOIN users u ON u.id=i.user_id WHERE 1=1"; args=[]
    if q: sql+=" AND (i.title LIKE ? OR i.description LIKE ? OR i.location LIKE ?)"; args += [f"%{q}%"]*3
    if typ in ("lost","found"): sql+=" AND i.post_type=?"; args.append(typ)
    if cat: sql+=" AND i.category=?"; args.append(cat)
    if loc: sql+=" AND i.location=?"; args.append(loc)
    if status in ("open","claimed","resolved","closed"): sql+=" AND i.status=?"; args.append(status)
    sql+=" ORDER BY i.id DESC"
    rows=db().execute(sql,args).fetchall()
    return render_template("items.html",items=rows,q=q,typ=typ,cat=cat,loc=loc,status=status)
@app.route("/items/new",methods=["GET","POST"])
@login_required
def new_item():
    if request.method=="POST":
        typ=request.form.get("post_type"); title=request.form.get("title","").strip(); cat=request.form.get("category"); desc=request.form.get("description","").strip(); loc=request.form.get("location"); date=request.form.get("item_date")
        image=request.files.get("image"); filename=None
        if typ not in ("lost","found") or not title or not desc or not date or cat not in CATEGORIES or loc not in LOCATIONS:
            flash("બધી જરૂરી વિગતો યોગ્ય રીતે भरो.","danger"); return render_template("new_item.html",today=datetime.now().strftime("%Y-%m-%d"))
        if image and image.filename:
            ext=image.filename.rsplit(".",1)[-1].lower()
            if ext not in ("png","jpg","jpeg","webp"): flash("ફક્ત PNG/JPG/WEBP ફોટો માન્ય છે.","danger"); return render_template("new_item.html",today=date)
            filename=datetime.now().strftime("%Y%m%d%H%M%S%f")+"_"+secure_filename(image.filename); image.save(os.path.join(UPLOAD,filename))
        cur=db().execute("INSERT INTO items(user_id,post_type,title,category,description,location,item_date,image_filename,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(user()["id"],typ,title,cat,desc,loc,date,filename,"open",now())); db().commit(); iid=cur.lastrowid
        new=db().execute("SELECT * FROM items WHERE id=?",(iid,)).fetchone(); opposite="found" if typ=="lost" else "lost"
        for other in db().execute("SELECT * FROM items WHERE post_type=? AND status='open' AND id<>?",(opposite,iid)).fetchall():
            sc,why=score(new,other)
            if sc>=35:
                notify(other["user_id"],f"Possible match: {title} ({sc}%)",url_for("detail",iid=iid))
                notify(user()["id"],f"Possible match: {other['title']} ({sc}%)",url_for("detail",iid=other["id"]))
        flash("તમારી પોસ્ટ ઉમેરાઈ ગઈ.","success"); return redirect(url_for("detail",iid=iid))
    return render_template("new_item.html",today=datetime.now().strftime("%Y-%m-%d"))
@app.route("/items/<int:iid>")
def detail(iid):
    item=db().execute("SELECT i.*,u.name poster_name FROM items i JOIN users u ON u.id=i.user_id WHERE i.id=?",(iid,)).fetchone()
    if not item: abort(404)
    matches=[]
    if item["status"]=="open":
        op="found" if item["post_type"]=="lost" else "lost"
        for other in db().execute("SELECT i.*,u.name poster_name FROM items i JOIN users u ON u.id=i.user_id WHERE i.post_type=? AND i.status='open' AND i.id<>?",(op,iid)).fetchall():
            sc,why=score(item,other)
            if sc>=25: matches.append({"item":other,"score":sc,"why":why})
        matches=sorted(matches,key=lambda x:x["score"],reverse=True)[:5]
    return render_template("detail.html",item=item,matches=matches)
@app.route("/items/<int:iid>/claim",methods=["POST"])
@login_required
def claim(iid):
    item=db().execute("SELECT * FROM items WHERE id=?",(iid,)).fetchone()
    if not item: abort(404)
    msg=request.form.get("message","").strip()
    if item["user_id"]==user()["id"] or item["status"]!="open" or len(msg)<10:
        flash("Claim કરી શકાતી નથી. પોતાની પોસ્ટ નહીં અને ઓછામાં ઓછું 10 અક્ષરનું verification detail લખો.","warning"); return redirect(url_for("detail",iid=iid))
    db().execute("INSERT INTO claims(item_id,claimant_id,message,status,created_at) VALUES(?,?,?,?,?)",(iid,user()["id"],msg,"pending",now())); db().commit()
    notify(item["user_id"],f"{user()['name']} sent a claim for {item['title']}",url_for("claims"))
    flash("Claim Request મોકલાઈ ગઈ.","success"); return redirect(url_for("claims"))
@app.route("/claims")
@login_required
def claims():
    u=user()
    rows=db().execute("""SELECT c.*,i.title,i.user_id owner_id,u.name claimant_name,owner.name owner_name FROM claims c JOIN items i ON i.id=c.item_id JOIN users u ON u.id=c.claimant_id JOIN users owner ON owner.id=i.user_id WHERE c.claimant_id=? OR i.user_id=? ORDER BY c.id DESC""",(u["id"],u["id"])).fetchall()
    return render_template("claims.html",claims=rows)
@app.route("/claims/<int:cid>",methods=["POST"])
@login_required
def review(cid):
    c=db().execute("SELECT c.*,i.user_id owner_id,i.title FROM claims c JOIN items i ON i.id=c.item_id WHERE c.id=?",(cid,)).fetchone()
    if not c: abort(404)
    if user()["role"]!="admin" and user()["id"]!=c["owner_id"]: abort(403)
    action=request.form.get("action")
    if action not in ("approved","rejected"): abort(400)
    db().execute("UPDATE claims SET status=? WHERE id=?",(action,cid))
    if action=="approved": db().execute("UPDATE items SET status='claimed' WHERE id=(SELECT item_id FROM claims WHERE id=?)",(cid,))
    db().commit(); notify(c["claimant_id"],f"Claim for {c['title']} was {action}.",url_for("claims")); flash("Claim status અપડેટ થયું.","success"); return redirect(url_for("claims"))
@app.route("/items/<int:iid>/resolve",methods=["POST"])
@login_required
def resolve(iid):
    item=db().execute("SELECT * FROM items WHERE id=?",(iid,)).fetchone()
    if not item: abort(404)
    if user()["role"]!="admin" and user()["id"]!=item["user_id"]: abort(403)
    db().execute("UPDATE items SET status='resolved' WHERE id=?",(iid,)); db().commit(); flash("Item resolved mark થયું.","success"); return redirect(url_for("detail",iid=iid))
@app.route("/notifications")
@login_required
def notifications():
    rows=db().execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC",(user()["id"],)).fetchall()
    db().execute("UPDATE notifications SET is_read=1 WHERE user_id=?",(user()["id"],)); db().commit()
    return render_template("notifications.html",rows=rows)
@app.route("/admin")
@admin_required
def admin():
    users=db().execute("SELECT id,name,email,role FROM users ORDER BY id DESC").fetchall()
    items=db().execute("SELECT i.*,u.name poster_name FROM items i JOIN users u ON u.id=i.user_id ORDER BY i.id DESC").fetchall()
    claims_=db().execute("SELECT c.*,i.title,u.name claimant_name FROM claims c JOIN items i ON i.id=c.item_id JOIN users u ON u.id=c.claimant_id ORDER BY c.id DESC").fetchall()
    return render_template("admin.html",users=users,items=items,claims=claims_)
@app.route("/admin/item/<int:iid>",methods=["POST"])
@admin_required
def admin_item(iid):
    status=request.form.get("status")
    if status not in ("open","claimed","resolved","closed"): abort(400)
    db().execute("UPDATE items SET status=? WHERE id=?",(status,iid)); db().commit(); flash("Status અપડેટ થયું.","success"); return redirect(url_for("admin"))
@app.route("/admin/user/<int:uid>",methods=["POST"])
@admin_required
def admin_user(uid):
    role=request.form.get("role")
    if role not in ("admin","student"): abort(400)
    db().execute("UPDATE users SET role=? WHERE id=?",(role,uid)); db().commit(); flash("Role અપડેટ થયું.","success"); return redirect(url_for("admin"))
@app.route("/export.csv")
@admin_required
def export():
    rows=db().execute("SELECT i.id,u.name,i.post_type,i.title,i.category,i.description,i.location,i.item_date,i.status,i.created_at FROM items i JOIN users u ON u.id=i.user_id ORDER BY i.id DESC").fetchall()
    s=io.StringIO(); w=csv.writer(s); w.writerow(["ID","Poster","Type","Title","Category","Description","Location","Date","Status","Created At"])
    for r in rows: w.writerow(list(r))
    out=io.BytesIO(s.getvalue().encode("utf-8-sig")); out.seek(0)
    return send_file(out,mimetype="text/csv",as_attachment=True,download_name="campus_lost_found_report.csv")
@app.errorhandler(403)
def forbidden(e): return render_template("error.html",code=403,message="આ પેજ જોવા માટે પરવાનગી નથી."),403
@app.errorhandler(404)
def missing(e): return render_template("error.html",code=404,message="આ પેજ અથવા વસ્તુ મળી નથી."),404
if __name__=="__main__":
    init_db()
    print("CampusFind running at http://127.0.0.1:5000")
    print("Admin: admin@campus.local / Admin@123")
    app.run(debug=True)
