"""
コンテンツ公開サービス
Firebase Firestore + Cloud Run Drive API を使用して
研修コンテンツを Personal Video Platform に公開する
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

import httpx
import firebase_admin
from firebase_admin import credentials, auth, firestore

logger = logging.getLogger(__name__)

# レベルプレフィックスの順序マッピング
# intro/beginner(入門) → basic/elementary(初級) → intermediate(中級) → advanced(上級)
LEVEL_ORDER = {
    'intro': 0, 'introduction': 0, 'beginner': 0,
    'basic': 1, 'elementary': 1,
    'intermediate': 2,
    'advanced': 3,
}


def get_topic_sort_key(topic: Dict[str, Any]) -> tuple:
    """トピックのソートキーを生成（レベル→章→話の順）

    対応パターン:
      A: intro-1-1, basic-2-3, advanced_1-1  (レベルプレフィックス)
      B: beginner/0-1_intro (レベルサブフォルダ)
      C: 01-01_xxx (2階層数値)
      D: 1-1-1_xxx (3階層数値)
    """
    subfolder = topic.get('subfolder', '') or ''
    base_name = topic.get('base_name', '')
    level_order = 0

    # サブフォルダからレベル検出
    if subfolder:
        folder = subfolder.split('/')[-1].lower()
        level_order = LEVEL_ORDER.get(folder, 0)

    # パターンA: レベルプレフィックス "intro-1-1", "advanced_2-3"
    m = re.match(r'^([a-zA-Z]+)[-_](\d+)[-_](\d+)', base_name)
    if m:
        level_order = LEVEL_ORDER.get(m.group(1).lower(), 99)
        return (level_order, int(m.group(2)), int(m.group(3)), base_name)

    # パターンD: 3階層数値 "1-1-1_title"
    m = re.match(r'^(\d+)[-_](\d+)[-_](\d+)', base_name)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)), base_name)

    # パターンC: 2階層数値 "01-01_title"
    m = re.match(r'^(\d+)[-_](\d+)', base_name)
    if m:
        return (level_order, int(m.group(1)), int(m.group(2)), base_name)

    return (99, 0, 0, base_name)


def extract_episode_number(base_name: str) -> str | None:
    """ファイル名からエピソード番号を抽出

    Returns:
      "intro-1-1", "1-2", "1-1-1" 等。マッチしなければ None
    """
    # パターンA: レベルプレフィックス "intro-1-1", "advanced_2-3"
    m = re.match(r'^([a-zA-Z]+)[-_](\d+)[-_](\d+)', base_name)
    if m:
        level = m.group(1).lower()
        return f"{level}-{int(m.group(2))}-{int(m.group(3))}"

    # パターンD: 3階層数値 "1-1-1_title"
    m = re.match(r'^(\d+)[-_](\d+)[-_](\d+)', base_name)
    if m:
        return f"{int(m.group(1))}-{int(m.group(2))}-{int(m.group(3))}"

    # パターンC: 2階層数値 "01-01_title"
    m = re.match(r'^(\d+)[-_](\d+)', base_name)
    if m:
        return f"{int(m.group(1))}-{int(m.group(2))}"

    return None


# Firebase設定
FIREBASE_SA_KEY_PATH = (
    Path.home() / ".config/ai-agents/credentials/firebase/personal-video-platform-sa.json"
)
FIREBASE_API_KEY = "AIzaSyAh6IOiDc0DdtsZkbxqvEhaFRy9P0VZSw8"
CLOUD_RUN_URL = "https://pvp-drive-api-153069559514.asia-northeast1.run.app"
SERVICE_UID = "tracker-publish-service"


@dataclass
class PublishResult:
    """公開結果"""
    success: bool = False
    classroom_id: str = ""
    total_contents: int = 0
    uploaded_contents: int = 0
    skipped_contents: int = 0
    errors: List[str] = field(default_factory=list)
    details: List[Dict[str, Any]] = field(default_factory=list)


class PublishService:
    """コンテンツ公開サービス"""

    def __init__(self):
        self._firebase_app: Optional[firebase_admin.App] = None
        self._firestore_client = None
        self._id_token: Optional[str] = None

    def _init_firebase(self):
        """Firebase Admin SDK初期化"""
        if self._firebase_app:
            return

        if not FIREBASE_SA_KEY_PATH.exists():
            raise RuntimeError(
                f"Firebase SA key not found: {FIREBASE_SA_KEY_PATH}\n"
                "Please create a service account key for personal-video-platform."
            )

        cred = credentials.Certificate(str(FIREBASE_SA_KEY_PATH))

        # 既存のアプリ名チェック
        try:
            self._firebase_app = firebase_admin.get_app('pvp-publisher')
        except ValueError:
            self._firebase_app = firebase_admin.initialize_app(
                cred,
                {'projectId': 'personal-video-platform'},
                name='pvp-publisher'
            )

        self._firestore_client = firestore.client(app=self._firebase_app)
        logger.info("Firebase Admin SDK initialized for publishing")

    async def _get_id_token(self) -> str:
        """Firebase ID Token取得（カスタムトークン→IDトークン交換）"""
        custom_token = auth.create_custom_token(
            SERVICE_UID,
            app=self._firebase_app
        )

        token_str = custom_token.decode('utf-8') if isinstance(custom_token, bytes) else custom_token

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={FIREBASE_API_KEY}",
                json={
                    "token": token_str,
                    "returnSecureToken": True
                }
            )
            resp.raise_for_status()
            data = resp.json()
            self._id_token = data["idToken"]
            return self._id_token

    async def _upload_file(
        self, file_path: Path, classroom_id: str, content_type: str
    ) -> Dict[str, str]:
        """Cloud Run API経由でファイルをDriveにアップロード"""
        token = self._id_token or await self._get_id_token()

        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(file_path, 'rb') as f:
                files = {'file': (file_path.name, f, content_type)}
                resp = await client.post(
                    f"{CLOUD_RUN_URL}/upload",
                    params={"classroom_id": classroom_id},
                    headers={"Authorization": f"Bearer {token}"},
                    files=files
                )

                # トークン期限切れの場合はリトライ
                if resp.status_code == 401:
                    token = await self._get_id_token()
                    f.seek(0)
                    files = {'file': (file_path.name, f, content_type)}
                    resp = await client.post(
                        f"{CLOUD_RUN_URL}/upload",
                        params={"classroom_id": classroom_id},
                        headers={"Authorization": f"Bearer {token}"},
                        files=files
                    )

                resp.raise_for_status()
                return resp.json()

    # サブフォルダ名の表示用マッピング
    SUBFOLDER_DISPLAY_NAMES = {
        'intro': '入門',
        'introduction': '入門',
        'beginner': '入門',
        'basic': '初級',
        'elementary': '初級',
        'intermediate': '中級',
        'advanced': '上級',
    }

    def _find_or_create_classroom(
        self, name: str, parent_id: str = None, depth: int = 0, order: int = 0,
        access_type: str = 'public'
    ) -> str:
        """Firestoreでクラスルームを検索または作成（親子教室対応）"""
        classrooms_ref = self._firestore_client.collection('classrooms')

        # 検索条件: 名前が一致 + 親教室が一致
        query = classrooms_ref.where('name', '==', name)
        if parent_id:
            query = query.where('parentClassroomId', '==', parent_id)
        else:
            # ルート教室の場合、parentClassroomId が null のものを探す
            pass
        query = query.limit(1)
        docs = list(query.get())

        # 親教室指定ありの場合、同名の別ルート教室を誤マッチしないよう確認
        if docs and parent_id:
            doc = docs[0]
            if doc.to_dict().get('parentClassroomId') != parent_id:
                docs = []
        elif docs and not parent_id:
            doc = docs[0]
            if doc.to_dict().get('parentClassroomId'):
                docs = []

        if docs:
            doc = docs[0]
            doc_data = doc.to_dict()
            # 既存教室のaccessType/isActiveを検証・修正
            updates = {}
            if doc_data.get('accessType') != access_type:
                updates['accessType'] = access_type
                logger.warning(f"Classroom {doc.id} had accessType='{doc_data.get('accessType')}', fixing to '{access_type}'")
            if not doc_data.get('isActive'):
                updates['isActive'] = True
                logger.warning(f"Classroom {doc.id} was inactive, fixing to active")
            if doc_data.get('freeEpisodeCount') is None:
                updates['freeEpisodeCount'] = 5
            if updates:
                updates['updatedAt'] = datetime.utcnow()
                classrooms_ref.document(doc.id).update(updates)
                logger.info(f"Updated classroom {doc.id}: {list(updates.keys())}")
            logger.info(f"Found existing classroom: {doc.id} ({name})")
            return doc.id

        now = datetime.utcnow()
        _, doc_ref = classrooms_ref.add({
            'name': name,
            'description': f'{name} - 自動公開',
            'accessType': access_type,
            'parentClassroomId': parent_id,
            'depth': depth,
            'childCount': 0,
            'contentCount': 0,
            'freeEpisodeCount': 5,
            'order': order,
            'isActive': True,
            'createdBy': SERVICE_UID,
            'createdAt': now,
            'updatedAt': now
        })

        # 親教室の childCount を更新
        if parent_id:
            parent_ref = classrooms_ref.document(parent_id)
            parent_data = parent_ref.get().to_dict()
            parent_ref.update({
                'childCount': (parent_data.get('childCount', 0) or 0) + 1,
                'updatedAt': now
            })

        logger.info(f"Created new classroom: {doc_ref.id} ({name}, parent={parent_id}, depth={depth})")
        return doc_ref.id

    def _get_subfolder_display_name(self, subfolder: str) -> str:
        """サブフォルダ名を表示用の日本語名に変換"""
        folder = subfolder.split('/')[-1].lower()
        return self.SUBFOLDER_DISPLAY_NAMES.get(folder, subfolder)

    def _get_existing_contents(self, classroom_id: str) -> Dict[str, Dict[str, str]]:
        """既存コンテンツを取得（episodeNumber/order/title → ドキュメントID）"""
        contents_ref = self._firestore_client.collection('contents')
        docs = contents_ref.where('classroomId', '==', classroom_id).get()
        result = {
            'by_episode': {},  # episodeNumber → doc_id
            'by_order': {},    # order → doc_id
            'by_title': {},    # title → doc_id
        }
        for doc in docs:
            data = doc.to_dict()
            ep = data.get('episodeNumber')
            order = data.get('order')
            title = data.get('title', '')
            info = {'id': doc.id, 'htmlContent': data.get('htmlContent', '')}
            if ep:
                result['by_episode'][ep] = info
            if order is not None:
                result['by_order'][order] = info
            if title:
                result['by_title'][title] = info
        return result

    async def publish_project(
        self,
        project_name: str,
        project_path: str,
        topics: List[Dict[str, Any]],
        progress_callback=None,
        access_type: str = 'public'
    ) -> PublishResult:
        """プロジェクトのコンテンツを公開（サブフォルダ→子教室対応）"""
        result = PublishResult()

        try:
            self._init_firebase()

            # IDトークンを事前取得（全アップロードで再利用）
            await self._get_id_token()

            # ルート教室を作成/取得
            root_classroom_id = self._find_or_create_classroom(project_name, access_type=access_type)
            result.classroom_id = root_classroom_id

            # 公開対象トピック（HTML or MP3が存在するもの）
            content_path = Path(project_path) / "content"
            publishable = [t for t in topics if t.get('has_html') or t.get('has_mp3')]

            # レベル対応ソート（入門→初級→中級→上級、章→話の順）
            publishable.sort(key=get_topic_sort_key)
            result.total_contents = len(publishable)

            # サブフォルダ別にグループ化
            subfolders = []
            seen_subfolders = set()
            for t in publishable:
                sf = t.get('subfolder', '') or ''
                if sf not in seen_subfolders:
                    seen_subfolders.add(sf)
                    subfolders.append(sf)

            # サブフォルダが複数ある場合のみ子教室を作成
            has_subfolders = len(subfolders) > 1 or (len(subfolders) == 1 and subfolders[0] != '')
            use_child_classrooms = has_subfolders and any(sf != '' for sf in subfolders)

            # サブフォルダ → 教室IDのマッピング
            subfolder_classroom_map = {}
            subfolder_existing_contents = {}

            if use_child_classrooms:
                for child_order, sf in enumerate(subfolders):
                    if sf == '':
                        # サブフォルダなしのトピックはルート教室に配置
                        subfolder_classroom_map[''] = root_classroom_id
                    else:
                        display_name = self._get_subfolder_display_name(sf)
                        child_name = f"{project_name} - {display_name}"
                        child_id = self._find_or_create_classroom(
                            child_name,
                            parent_id=root_classroom_id,
                            depth=1,
                            order=child_order,
                            access_type=access_type
                        )
                        subfolder_classroom_map[sf] = child_id
                        logger.info(f"Child classroom: {child_name} → {child_id}")
            else:
                # サブフォルダなし or 単一 → 全てルート教室に配置
                for sf in subfolders:
                    subfolder_classroom_map[sf] = root_classroom_id

            # 各教室の既存コンテンツを取得
            for sf, cid in subfolder_classroom_map.items():
                if cid not in subfolder_existing_contents:
                    subfolder_existing_contents[cid] = self._get_existing_contents(cid)

            contents_ref = self._firestore_client.collection('contents')

            # 教室別の order カウンター
            classroom_order_counter = {}
            classroom_content_counter = {}

            for global_order, topic in enumerate(publishable):
                base_name = topic.get('base_name', '')
                title = topic.get('title', '') or base_name
                subfolder = topic.get('subfolder', '') or ''

                # この topic が所属する教室
                target_classroom_id = subfolder_classroom_map.get(subfolder, root_classroom_id)

                # 教室内の order を管理
                if target_classroom_id not in classroom_order_counter:
                    classroom_order_counter[target_classroom_id] = 0
                    classroom_content_counter[target_classroom_id] = 0
                order = classroom_order_counter[target_classroom_id]
                classroom_order_counter[target_classroom_id] += 1

                # エピソード番号を抽出（レベルプレフィックス対応）
                episode_number = extract_episode_number(base_name)

                # サブフォルダ対応
                actual_path = content_path / subfolder if subfolder else content_path

                try:
                    html_file_id = None
                    html_url = None
                    mp3_file_id = None
                    mp3_url = None
                    html_content = None

                    # HTML アップロード
                    html_path = actual_path / f"{base_name}.html"
                    if html_path.exists():
                        upload = await self._upload_file(html_path, target_classroom_id, 'text/html')
                        html_file_id = upload.get('file_id')
                        html_url = upload.get('url')
                        try:
                            html_content = html_path.read_text(encoding='utf-8')
                        except Exception:
                            pass

                    # タイトルに日本語が含まれない場合（ローマ字ファイル名由来）、HTMLの<h1>から日本語タイトルを抽出
                    has_japanese = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', title))
                    if not has_japanese and html_content:
                        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html_content, re.DOTALL | re.IGNORECASE)
                        if h1_match:
                            extracted = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
                            if extracted:
                                logger.info(f"Title extracted from <h1>: '{title}' → '{extracted}'")
                                title = extracted

                    # MP3 アップロード
                    mp3_path = actual_path / f"{base_name}.mp3"
                    if mp3_path.exists():
                        upload = await self._upload_file(mp3_path, target_classroom_id, 'audio/mpeg')
                        mp3_file_id = upload.get('file_id')
                        mp3_url = upload.get('download_url')

                    # Firestoreにコンテンツ登録/更新
                    now = datetime.utcnow()
                    content_data = {
                        'title': title,
                        'description': '',
                        'classroomId': target_classroom_id,
                        'htmlFileId': html_file_id,
                        'htmlContent': html_content,
                        'htmlUrl': html_url,
                        'mp3FileId': mp3_file_id,
                        'mp3Url': mp3_url,
                        'duration': (topic.get('mp3_duration_ms', 0) or 0) / 1000,
                        'order': order,
                        'episodeNumber': episode_number,
                        'isActive': True,
                        'updatedAt': now,
                    }

                    # 既存コンテンツの照合: episodeNumber → title の優先順
                    existing = subfolder_existing_contents.get(target_classroom_id, {})
                    existing_info = (
                        existing.get('by_episode', {}).get(episode_number)
                        or existing.get('by_title', {}).get(title)
                    )
                    if existing_info:
                        existing_doc_id = existing_info['id']
                        # HTML内容が変更された場合のみ contentUpdatedAt をセット
                        if html_content and html_content != existing_info.get('htmlContent', ''):
                            content_data['contentUpdatedAt'] = now
                        contents_ref.document(existing_doc_id).update(content_data)
                    else:
                        content_data['createdBy'] = SERVICE_UID
                        content_data['createdAt'] = now
                        contents_ref.add(content_data)

                    result.uploaded_contents += 1
                    classroom_content_counter[target_classroom_id] = \
                        classroom_content_counter.get(target_classroom_id, 0) + 1
                    result.details.append({
                        'title': title,
                        'status': 'success',
                        'html': bool(html_file_id),
                        'mp3': bool(mp3_file_id)
                    })

                    logger.info(f"Published: {title} → classroom={target_classroom_id} (HTML={bool(html_file_id)}, MP3={bool(mp3_file_id)})")

                    if progress_callback:
                        await progress_callback(global_order + 1, result.total_contents, title)

                except Exception as e:
                    error_msg = f"{title}: {str(e)}"
                    result.errors.append(error_msg)
                    result.details.append({
                        'title': title,
                        'status': 'error',
                        'error': str(e)
                    })
                    logger.error(f"Failed to publish {title}: {e}")

            # 各教室のcontentCountを更新
            now = datetime.utcnow()
            for cid, count in classroom_content_counter.items():
                self._firestore_client.collection('classrooms').document(cid).update({
                    'contentCount': count,
                    'updatedAt': now
                })

            # RAG インデックスデータのアップロード（サブコレクション方式）
            rag_index_path = Path(project_path) / "rag_index.json"
            if rag_index_path.exists():
                try:
                    with open(rag_index_path, 'r', encoding='utf-8') as f:
                        rag_index_data = json.load(f)

                    # ルート教室に ragEnabled フラグを設定
                    self._firestore_client.collection('classrooms').document(root_classroom_id).update({
                        'ragEnabled': True,
                        'updatedAt': datetime.utcnow()
                    })
                    logger.info(f"Set ragEnabled=True on classroom {root_classroom_id}")

                    # ragIndexes/{classroomId} にメタデータを書き込み
                    rag_doc_ref = self._firestore_client.collection('ragIndexes').document(root_classroom_id)
                    now = datetime.utcnow()

                    chunks = rag_index_data.get('chunks', [])

                    rag_doc_data = {
                        'classroomId': root_classroom_id,
                        'courseName': project_name,
                        'embeddingModel': rag_index_data.get('embedding_model', ''),
                        'generationModel': rag_index_data.get('generation_model', ''),
                        'chunkCount': len(chunks),
                        'systemPrompt': f'あなたは「{project_name}」の学習アシスタントです。講座の内容に基づいて正確に回答してください。',
                        'updatedAt': now,
                    }

                    # ドキュメントが存在しなければ createdAt を追加
                    existing_doc = rag_doc_ref.get()
                    if not existing_doc.exists:
                        rag_doc_data['createdAt'] = now

                    rag_doc_ref.set(rag_doc_data, merge=True)
                    logger.info(f"Wrote RAG index metadata to ragIndexes/{root_classroom_id}")

                    # 既存チャンクを削除（再アップロード対応）
                    chunks_ref = rag_doc_ref.collection('chunks')
                    existing_chunks = chunks_ref.list_documents()
                    batch = self._firestore_client.batch()
                    delete_count = 0
                    for doc_ref in existing_chunks:
                        batch.delete(doc_ref)
                        delete_count += 1
                        # Firestore batch は最大500操作
                        if delete_count % 450 == 0:
                            batch.commit()
                            batch = self._firestore_client.batch()
                    if delete_count > 0:
                        batch.commit()
                        logger.info(f"Deleted {delete_count} existing chunks")

                    # チャンクをサブコレクションに書き込み（バッチ処理）
                    # 各チャンクに3072次元のembedding（約24KB）があるため
                    # Firestoreの10MBトランザクション制限を回避するためバッチサイズを小さくする
                    CHUNK_BATCH_SIZE = 20
                    batch = self._firestore_client.batch()
                    write_count = 0
                    batch_count = 0
                    for chunk in chunks:
                        chunk_id = chunk.get('id', f"chunk_{write_count:03d}")
                        chunk_doc_ref = chunks_ref.document(chunk_id)
                        batch.set(chunk_doc_ref, {
                            'text': chunk.get('text', ''),
                            'embedding': chunk.get('embedding', []),
                            'metadata': chunk.get('metadata', {}),
                        })
                        write_count += 1
                        batch_count += 1
                        if batch_count >= CHUNK_BATCH_SIZE:
                            batch.commit()
                            batch = self._firestore_client.batch()
                            batch_count = 0
                            logger.info(f"Wrote {write_count}/{len(chunks)} chunks...")

                    # 残りをコミット
                    if batch_count > 0:
                        batch.commit()

                    logger.info(f"Uploaded {write_count} chunks to ragIndexes/{root_classroom_id}/chunks/")

                except Exception as e:
                    logger.error(f"Failed to upload RAG index data: {e}")
                    result.errors.append(f"RAGインデックスアップロード失敗: {str(e)}")
            else:
                # rag_index.json がない場合は ragEnabled を false に設定
                try:
                    self._firestore_client.collection('classrooms').document(root_classroom_id).update({
                        'ragEnabled': False,
                        'updatedAt': datetime.utcnow()
                    })
                except Exception:
                    pass

            result.success = result.uploaded_contents > 0

        except Exception as e:
            result.errors.append(f"公開処理エラー: {str(e)}")
            logger.error(f"Publish error: {e}", exc_info=True)

        return result


# シングルトン
_publish_service: Optional[PublishService] = None


def get_publish_service() -> PublishService:
    """PublishServiceインスタンスを取得"""
    global _publish_service
    if _publish_service is None:
        _publish_service = PublishService()
    return _publish_service
