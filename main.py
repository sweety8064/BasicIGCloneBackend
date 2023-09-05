import json
import uuid
from werkzeug.datastructures import FileStorage

from flask import Flask, jsonify, request, redirect, url_for, send_from_directory
import psycopg2
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from datetime import timedelta

db_host = "localhost"
db_port = "5432"
db_name = "instagramclone"
db_user = "postgres"
db_password = ""

conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_password)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret'

base_url = 'http://127.0.0.1:5000/'

jwt = JWTManager(app)  #Initialize the JWT manager:

def authenticate(username, password):
    # your authentication logic here
    user = {'username': username, 'password': password}
    return user

@jwt.user_identity_loader
def user_identity_lookup(user):
    return user['username']

@jwt.unauthorized_loader
def unauthorized_callback(callback):
    return jsonify({'error': 'Unauthorized access'}), 401

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({'error': 'Token has expired'}), 401

@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username', None)
    password = request.json.get('password', None)

    if username == 'admin' and password == 'admin':
        user = {'username': username, 'password': password}
        expires = timedelta(seconds=131)
        access_token = create_access_token(identity=user, expires_delta=expires)
        return jsonify({'access_token': access_token}), 200
    else:
        return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/data', methods=['POST'])
def get_data():
    data = request.get_json()
    cur = conn.cursor()

    sql = """
            SELECT 
                post.*, 
                users.name, 
                users.profile_image_uuid,
                post_date - INTERVAL '8 HOURS' AS post_date_utc0, 
                COUNT(likes.post_id) as total_like, 
                CASE WHEN EXISTS ( 
                  SELECT 1 FROM likes WHERE post.post_id = likes.post_id AND likes.user_uuid = %s AND user_islike = true
                ) THEN true ELSE false END AS user_islike 
            FROM post 
            INNER JOIN follow f ON post.user_uuid = f.following_uuid 
            JOIN users ON post.user_uuid = users.user_uuid 
            LEFT JOIN likes ON post.post_id = likes.post_id AND user_islike = true 
            WHERE f.follower_uuid = %s AND f.user_isfollow = 'true' 
            GROUP BY post.post_id, users.name, users.profile_image_uuid, post_date 
            UNION 
            SELECT 
                post.*, 
                users.name, 
                users.profile_image_uuid,
                post_date - INTERVAL '8 HOURS' AS post_date_utc0, 
                COUNT(likes.post_id) as total_like, 
                CASE WHEN EXISTS ( 
                  SELECT 1 FROM likes WHERE post.post_id = likes.post_id AND likes.user_uuid = %s AND user_islike = true
                ) THEN true ELSE false END AS user_islike 
            FROM post
            JOIN users ON post.user_uuid = users.user_uuid 
            LEFT JOIN likes ON post.post_id = likes.post_id AND user_islike = true 
            WHERE post.user_uuid = %s
            GROUP BY post.post_id, users.name, users.profile_image_uuid, post_date 
            ORDER BY post_date DESC
            LIMIT 5 OFFSET %s;
        """

    sqlData = (data['uid'], data['uid'], data['uid'], data['uid'], data['offset'])

    try:
        cur.execute(sql, sqlData)     #one parameter must be in []

        rows = cur.fetchall()
        json = []
        for row in rows:
            json.append({
                "post_id": row[0],
                "post_user_uuid": row[1],
                "post_date": row[2],
                "image_url": base_url + 'images/' + row[3] + '.jpg',
                "caption": row[4],
                "post_username": row[5],
                "user_image_url": base_url + 'profileimages/' + row[6] + '.jpg',
                "post_date_utc0": row[7],
                "total_like": row[8],
                "user_islike": row[9]
            })


        cur.close()
        return json

    except Exception as e:
        print("error executing sql!", e)
        cur.close()
        return "error executing sql!", 400


@app.route('/upload', methods=['POST'])
def upload():
    # ================= get json values ================================
    json_data = request.values['json']  # must match "name=" where in "Content-Disposition: form-data; name=\"jsonss\"
    data = json.loads(json_data)

    uid = data.get('uid')
    caption = data.get('caption')
    createDate = data.get('createDate')

    # ================= get image ================================
    file = request.files['image']

    # ================= save in postgressql database ================================
    photo_UUID = str(uuid.uuid4())
    photo_path = 'images/' + photo_UUID + '.jpg'

    sql = "INSERT INTO post (user_uuid, post_date, image_uuid, caption) VALUES (%s, %s, %s, %s)"
    data = (uid, createDate, photo_UUID, caption)  # actual values you want to insert

    cur = conn.cursor()

    try:
        cur.execute(sql, data)
        conn.commit()  # commit save for databse
        cur.close()

        if file:
            file.save(photo_path)  # default is jpg
            return 'Image uploaded successfully.'
        else:
            return 'No image uploaded.'
    except Exception as e:
        print("error executing sql!", e)
        cur.close()
        return "error executing sql!", 400

@app.route('/images/<image_path>')
def get_image(image_path):
    return send_from_directory('images/', image_path)

@app.route('/adduser', methods=['POST'])
def adduser():
    # ================= get json values ================================
    json_data = request.values['json']  # must match "name=" where in "Content-Disposition: form-data; name=\"jsonss\"
    data = json.loads(json_data)

    uid = data.get('uid')
    name = data.get('name')
    email = data.get('email')
    createDate = data.get('createDate')

    # ================= get image ================================
    profileImage = request.files['image']

    # ================= save in postgressql database ================================
    photo_UUID = str(uuid.uuid4())   # generated UUID for photo
    photo_path = 'ProfileImages/' + photo_UUID + '.jpg'

    sql = "INSERT INTO users (user_uuid, name, create_date, email, profile_image_uuid) VALUES (%s, %s, %s, %s, %s)"
    data = (data['uid'], data['name'], "NOW()", data['email'], photo_UUID)

    cur = conn.cursor()

    try:
        cur.execute(sql, data)
        conn.commit()  # commit save for databse
        cur.close()

        if profileImage:
            profileImage.save(photo_path)  #save the image, default is jpg
            return 'Image uploaded successfully.'
        else:
            return 'No image uploaded.'
    except Exception as e:
        print("error executing sql!", e)
        cur.close()
        return "error executing sql!", 400

@app.route('/users')     #get method without json
def fetchUsers():

    sql = "SELECT * FROM users;"
    cur = conn.cursor()
    cur.execute(sql)

    rows = cur.fetchall()
    json = []
    for row in rows:
        json.append({
            "user_uuid": row[0],
            "name": row[1],
            "create_date": row[2],
            "email": row[3],
            "profile_image_url": base_url + 'profileimages/' + row[4] + '.jpg'
        })

    cur.close()
    return json

@app.route('/user', methods=['POST'])     #get method without json
def fetchUser():
    data = request.get_json()

    sql = "SELECT * FROM users WHERE user_uuid like %s;"
    data = ([data['userUID']])

    cur = conn.cursor()
    cur.execute(sql, data)

    row = cur.fetchall()
    json = {
            "user_uuid": row[0][0],
            "name": row[0][1],
            "create_date": row[0][2],
            "email": row[0][3],
            "profile_image_url": base_url + 'profileimages/' + row[0][4] + '.jpg'
    }

    cur.close()
    return json

@app.route('/profileimages/<image_path>')
def getUserImage(image_path):
    return send_from_directory('ProfileImages/', image_path)


@app.route('/publicpost')
def publicpost():
    sql = "SELECT * FROM post;"

    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    json = []
    for row in rows:
        json.append({
            "post_id": row[0],
            "post_user_uuid": row[1],
            "post_date": row[2],
            "image_url": base_url + 'images/' + row[3] + '.jpg',
            "caption": row[4]
        })

    cur.close()

    return json

@app.route('/addlike', methods=['POST'])
def addLike():
    data = request.get_json()

    sql = """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM likes WHERE post_id = %s AND user_uuid = %s) THEN
            INSERT INTO likes (post_id, user_uuid, like_date, user_islike) VALUES (%s, %s, %s, %s);
        ELSE
            UPDATE likes
            SET user_islike = CASE WHEN user_islike = true THEN false ELSE true END
            WHERE post_id = %s AND user_uuid = %s;
        END IF;
    END$$;
    """

    data = (data['likePostUID'], data['userUID'],
            data['likePostUID'], data['userUID'], data['createDate'], 'true',
            data['likePostUID'], data['userUID'])

    cur = conn.cursor()
    cur.execute(sql, data)

    conn.commit()  # commit save for databse
    cur.close()

    return {"reponse": "success add like"}

@app.route('/addfollow', methods=['POST'])
def addFollow():
    data = request.get_json()

    sql = "INSERT INTO follow (follower_uuid, following_uuid, follow_time, user_isfollow) VALUES (%s, %s, %s, %s)"

    sql = """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM follow WHERE follower_uuid = %s AND following_uuid = %s) THEN
                INSERT INTO follow (follower_uuid, following_uuid, follow_time, user_isfollow) VALUES (%s, %s, %s, %s);
            ELSE
                UPDATE follow
                SET user_isfollow = CASE WHEN user_isfollow = true THEN false ELSE true END
                WHERE follower_uuid = %s AND following_uuid = %s;
            END IF;
        END$$;
        """

    data = (data['followerUUID'],
            data['followingUUID'],
            data['followerUUID'],
            data['followingUUID'],
            data['followTime'],
            'true',
            data['followerUUID'],
            data['followingUUID'])

    cur = conn.cursor()
    cur.execute(sql, data)
    conn.commit()
    cur.close()

    return {"reponse": "success add follow"}

@app.route('/fetchprofile', methods=['POST'])
def fetchProfile():
    data = request.get_json()

    sql = """
        Select * from follow f
        Where (f.follower_uuid = %s OR f.following_uuid = %s) AND f.user_isfollow = 'true';
    """

    data = (data['userUID'], data['userUID'])
    cur = conn.cursor()
    cur.execute(sql, data)

    rows = cur.fetchall()

    followerArray = []
    followingArray = []

    userUID = data[0]

    for row in rows:
        if row[1] == userUID:   # row[1] is following_uuid
            followerArray.append(row[0])
        elif row[0] == userUID:    # row[0] is follower_uuid
            followingArray.append(row[1])

    sql = """
    SELECT COUNT(users.user_uuid = post.user_uuid) FROM users
    LEFT JOIN post ON users.user_uuid = post.user_uuid
    GROUP BY users.user_uuid
    HAVING users.user_uuid = %s;
    """

    data = request.get_json()
    data = ([data['userUID']])
    cur.execute(sql, data)

    totalPost = cur.fetchone()[0]

    json = {
        "follower_uuid": followerArray,
        "following_uuid": followingArray,
        "total_post": totalPost
    }

    cur.close()
    return json

@app.route('/fetchprofilepost', methods=['POST'])
def fetchProfilePost():
    data = request.get_json()
    cur = conn.cursor()

    sql = """
                SELECT 
                    post.*, 
                    users.name, 
                    users.profile_image_uuid,
                    post_date - INTERVAL '8 HOURS' AS post_date_utc0, 
                    COUNT(likes.post_id) as total_like, 
                    CASE WHEN EXISTS ( 
                      SELECT 1 FROM likes WHERE post.post_id = likes.post_id AND likes.user_uuid = %s AND user_islike = true
                    ) THEN true ELSE false END AS user_islike 
                FROM post 
                JOIN users ON post.user_uuid = users.user_uuid 
                LEFT JOIN likes ON post.post_id = likes.post_id AND user_islike = true
                GROUP BY post.post_id, users.name, users.profile_image_uuid, post_date 
                HAVING post.user_uuid = %s 
                ORDER BY post_date DESC;
            """

    data = (data['userUID'], data['userUID'])

    try:
        cur.execute(sql, data)  # one parameter must be in []

        rows = cur.fetchall()
        json = []
        for row in rows:
            json.append({
                "post_id": row[0],
                "post_user_uuid": row[1],
                "post_date": row[2],
                "image_url": base_url + 'images/' + row[3] + '.jpg',
                "caption": row[4],
                "post_username": row[5],
                "user_image_url": base_url + 'profileimages/' + row[6] + '.jpg',
                "post_date_utc0": row[7],
                "total_like": row[8],
                "user_islike": row[9]
            })

        cur.close()
        return json

    except Exception as e:
        print("error executing sql!", e)
        cur.close()
        return "error executing sql!", 400

@app.route('/addcomment', methods=['POST'])
def addcomment():
    data = request.get_json()

    sql = "INSERT INTO comment (post_id, user_id, content, create_date) VALUES (%s, %s, %s, %s)"
    data = (data['post_id'], data['user_id'], data['comment_text'], data['comment_date'])

    cur = conn.cursor()
    cur.execute(sql, data)
    conn.commit()
    cur.close()

    return {"reponse": "success add message"}

@app.route('/fetchcomment', methods=['POST'])
def fetchComment():
    data = request.get_json()

    sql = """
        SELECT comment.*, users.name, users.profile_image_uuid, comment.create_date - INTERVAL '8 HOURS' AS create_date_utc0 FROM comment 
        INNER JOIN users ON comment.user_id = users.user_uuid 
        WHERE post_id = %s 
        ORDER BY create_date DESC;
    """
    data = data['post_id']

    cur = conn.cursor()

    try:
        cur.execute(sql, [data])  # one parameter must be in []

        rows = cur.fetchall()
        json = []
        for row in rows:
            json.append({
                "post_id": row[1],
                "user_id": row[2],
                "content": row[3],
                "create_date": row[4],
                "user_name": row[5],
                "user_image_url": base_url + 'profileimages/' + row[6] + '.jpg',
                "create_date_utc0": row[7]
            })

        cur.close()
        return json

    except Exception as e:
        print("error executing sql!", e)
        cur.close()
        return "error fetch comment!", 400

@app.route('/deletepost', methods=['POST'])
def deletePost():
    data = request.get_json()

    sql = "DELETE FROM post WHERE post_id = %s"
    data = data['post_id']

    cur = conn.cursor()

    try:
        cur.execute(sql, [data])  # one parameter must be in []

        conn.commit()
        cur.close()
        return "sucessfully delete!"

    except Exception as e:
        print("error executing sql!", e)
        cur.close()
        return "error delete post", 400

@app.route('/fetchfollower', methods=['POST'])
def fetchFollower():
    data = request.get_json()

    sql = """
                SELECT
                    u.*,
                    (f2.following_uuid IS NOT NULL AND f2.user_isfollow = 'true') AS is_following_back
                FROM
                    follow f1
                INNER JOIN
                    users u ON f1.follower_uuid = u.user_uuid
                LEFT JOIN
                    follow f2 ON f1.follower_uuid = f2.following_uuid AND f2.follower_uuid = %s
                WHERE
                    f1.following_uuid = %s AND f1.user_isfollow = TRUE
                ORDER BY
                    is_following_back DESC;
            """
    data = (data['session_user_uuid'], data['user_uuid'])

    cur = conn.cursor()

    try:
        cur.execute(sql, data)  # one parameter must be in []

        rows = cur.fetchall()
        json = []
        for row in rows:
            json.append({
                "user_uuid": row[0],
                "name": row[1],
                "create_date": row[2],
                "email": row[3],
                "profile_image_url": base_url + 'profileimages/' + row[4] + '.jpg',
                "is_following_back": row[5]
            })

        conn.commit()
        cur.close()
        return json

    except Exception as e:
        print("error executing sql!", e)
        cur.close()
        return "error fetching follower", 400

@app.route('/fetchfollowing', methods=['POST'])
def fetchFollowing():
    data = request.get_json()

    sql = """
            SELECT
                u.*,
                (f2.following_uuid IS NOT NULL AND f2.user_isfollow = 'true') AS is_following_back
            FROM
                follow f1
            INNER JOIN
                users u ON f1.following_uuid = u.user_uuid
            LEFT JOIN
                follow f2 ON f1.following_uuid = f2.following_uuid AND f2.follower_uuid = %s
            WHERE
                f1.follower_uuid = %s AND f1.user_isfollow = TRUE
            ORDER BY
                is_following_back DESC;
        """
    data = (data['session_user_uuid'], data['user_uuid'])

    cur = conn.cursor()

    try:
        cur.execute(sql, data)  # one parameter must be in []

        rows = cur.fetchall()
        json = []
        for row in rows:

            json.append({
                "user_uuid": row[0],
                "name": row[1],
                "create_date": row[2],
                "email": row[3],
                "profile_image_url": base_url + 'profileimages/' + row[4] + '.jpg',
                "is_following_back": row[5]
            })

        conn.commit()
        cur.close()
        return json

    except Exception as e:
        print("error executing sql!", e)
        cur.close()
        return "error fetching follower", 400

@app.route('/fetchuserslikepost', methods=['POST'])
def fetchUsersLikePost():
    data = request.get_json()

    sql = """
            SELECT
                u.*,
                (f.following_uuid IS NOT NULL AND f.user_isfollow = 'true') AS is_following_back
            FROM
                likes l
            INNER JOIN
                users u ON u.user_uuid = l.user_uuid
            LEFT JOIN
                follow f ON l.user_uuid = f.following_uuid AND f.follower_uuid = %s
            WHERE
                l.post_id = %s AND l.user_islike = TRUE
            ORDER BY
                is_following_back DESC;
        """
    data = (data['session_user_uuid'], data['post_id'])

    cur = conn.cursor()

    try:
        cur.execute(sql, data)  # one parameter must be in []

        rows = cur.fetchall()
        json = []
        for row in rows:

            json.append({
                "user_uuid": row[0],
                "name": row[1],
                "create_date": row[2],
                "email": row[3],
                "profile_image_url": base_url + 'profileimages/' + row[4] + '.jpg',
                "is_following_back": row[5]
            })

        conn.commit()
        cur.close()
        return json

    except Exception as e:
        print("error executing sql!", e)
        cur.close()
        return "error fetching follower", 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')


#curl -X POST -H "Content-Type: multipart/form-data; boundary=custom_boundary" -F 'json={"uid":"YKAdxeflgdNDM3ngAcIpe1qlXGU2","caption":"robot generated"}' -F "image=@/Users/sweety/Downloads/iron_ore.png" http://192.168.1.5:5000/upload