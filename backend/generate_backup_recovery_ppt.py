#!/usr/bin/env python3
"""
生成"バックアップとリカバリ～データベース安全管理の基本～"PPT
"""
from ppt_content_replacer import create_ppt_from_content

def create_backup_recovery_ppt():
    """生成备份和恢复PPT"""
    slides_content = [
        {
            'title': 'バックアップとリカバリ\n～データベース安全管理の基本～\n\n日々の運用トラブルに備える、必須のスキルを身につけましょう。'
        },
        {
            'title': 'バックアップとは何か',
            'content': '''バックアップとは、データベースの中身を「コピー」して安全な場所に保存することです。

これにより、万が一データが消えたり壊れたりしても、バックアップから元に戻せます。

**例：**
大事なファイルをUSBやクラウドに複製しておくのと同じです。

**重要性：**
バックアップデータは災害・障害・人為的ミスのリスクから守る"命綱"です。'''
        },
        {
            'title': 'なぜバックアップが必要か',
            'content': '''データベースは会社やサービスの"心臓部"です。

**主なリスク：**
- 操作ミスでテーブルやデータを削除してしまった時、復旧のためにはバックアップが必要です
- ハードウェア障害、ウイルス感染、ランサムウェア被害、災害（火事・地震）など、予想外のトラブルにも備えられます

**実例：**
管理者が間違えて```DELETE FROM users;```を実行 → バックアップがなければ復元不可'''
        },
        {
            'title': 'バックアップのタイミングと頻度',
            'content': '''**頻繁な更新システム：**
毎日1回フルバックアップ＋1時間ごとに増分バックアップが推奨されます。

**更新の少ないシステム：**
週1回や月1回でもOKですが、重要操作の前には必ず手動バックアップをしましょう。

**現場例：**
- ECサイトは毎晩3時に全データ自動バックアップ
- 会計ソフトは月末締め前に全データ保存

**MySQLでスケジュール自動化例（Linux cron）:**
```0 3 * * * mysqldump -u root -p'yourpass' shopdb > /backup/shopdb_$(date +\%F).sql```'''
        },
        {
            'title': 'バックアップの種類',
            'content': '''**フルバックアップ：**
すべてのデータや構造を一括保存
- 容量は大きいが復元が簡単

**増分バックアップ：**
前回のバックアップから変更された部分だけを保存
- データ増加量が少ない、復元時は複数ファイルを使う

**差分バックアップ：**
最初のフルバックアップ以降の変更分をまとめて保存

**図示イメージ例：**
1日目フル→2日目増分→3日目増分…
復元時はフル＋各増分を適用'''
        },
        {
            'title': 'MySQLのバックアップ方法：mysqldump',
            'content': '''mysqldumpは、最も一般的なMySQL用の論理バックアップツールです。

コマンド実行でテーブル構造やデータ内容をSQLファイルとして出力します。

**基本コマンド：**
```mysqldump -u ユーザー名 -p データベース名 > backup.sql```

**例：複数テーブルのみをバックアップ**
```mysqldump -u root -p mydb users orders > mydb_partial.sql```

**オプション例：**
- ```--single-transaction```（InnoDBの場合ロックを防ぐ）
- ```--routines```（ストアドプロシージャもバックアップ）'''
        },
        {
            'title': 'MySQLのバイナリログ（binlog）',
            'content': '''binlog（バイナリログ）は、全ての変更操作（INSERT/UPDATE/DELETE）を記録したファイルです。

mysqldumpのフルバックアップとbinlogを組み合わせることで、ほぼリアルタイムに近い復元が可能です。

**有効化例（my.cnfに記述）：**
```[mysqld]
log-bin=mysql-bin```

**binlogのリストを確認するコマンド：**
```SHOW BINARY LOGS;```

**特定の時点までリカバリ（mysqlbinlog利用例）：**
```mysqlbinlog --stop-datetime="2025-07-01 11:00:00" mysql-bin.000123 | mysql -u root -p mydb```'''
        },
        {
            'title': 'MySQLでのリカバリ手順（実例）',
            'content': '''**STEP1:** mysqldumpで取得したバックアップSQLファイルをリストア

```mysql -u ユーザー名 -p データベース名 < backup.sql```

**STEP2:** 必要に応じてbinlogを適用し、削除前や障害発生直前の状態まで復元

```mysqlbinlog --stop-datetime="2025-07-01 10:59:59" mysql-bin.000123 | mysql -u root -p mydb```

**応用例：**
1日前の状態に戻してから、その後の変更のみ再適用し、ピンポイントで復元'''
        },
        {
            'title': 'Oracleのバックアップ方法：EXP/IMP',
            'content': '''EXP（エクスポート）コマンドでデータベースや表を.dmpファイルとして出力します。

IMP（インポート）コマンドで.dmpファイルからデータをDBに戻します。

**全データベースエクスポート例：**
```exp ユーザー名/パスワード@接続識別子 FULL=Y FILE=fullbackup.dmp```

**特定テーブルのみエクスポート例：**
```exp ユーザー名/パスワード@接続識別子 TABLES=(EMP,DEPT) FILE=tables.dmp```

**インポート例：**
```imp ユーザー名/パスワード@接続識別子 FILE=tables.dmp```'''
        },
        {
            'title': 'Oracleの物理バックアップ：RMAN',
            'content': '''**RMAN（Recovery Manager）**は、Oracle公式の強力なバックアップ・リカバリツールです。

論理ではなく、物理ファイルそのものをバックアップするので、速度・信頼性が高いです。

**RMAN起動例（コマンドプロンプトから）：**
```rman target /```

**データベース全体のバックアップ例：**
```RMAN> BACKUP DATABASE;```

**特徴：**
- 増分バックアップや自動スケジューリングも可能
- クラウド連携や圧縮、暗号化など多様な機能もサポート'''
        },
        {
            'title': 'Oracleでのリカバリ手順（実例）',
            'content': '''**EXP/IMP利用例：**
事前にエクスポートした.dmpファイルからデータ復旧

```imp ユーザー名/パスワード@接続識別子 FILE=backup.dmp FROMUSER=olduser TOUSER=newuser```

**RMAN利用例：**
データベース全体をバックアップから復元

```RMAN> RESTORE DATABASE;
RMAN> RECOVER DATABASE;```

**時点リカバリ：**
「どこまで戻すか」を指定して部分復旧も可能'''
        },
        {
            'title': 'バックアップ・リカバリ時の注意点',
            'content': '''**保管場所：**
バックアップファイルは異なる物理場所（例：外付けHDD・クラウドストレージ）にも必ず保管

**セキュリティ：**
アクセス権限の設定（不用意にファイルを漏洩させない）

**検証：**
バックアップが正しく復元できるか、定期的にテストを行う

**管理：**
ファイル名に日付・バージョンを入れて管理すると便利

**例：**
- backup_20250701.sql
- fullbackup_20250701.dmp'''
        },
        {
            'title': '日常業務でのバックアップ活用例',
            'content': '''**開発現場：**
開発環境で新機能テスト前、必ず現状のバックアップを取得

**本番運用：**
業務システムでは毎晩自動バックアップ＋binlogやRMANで細かい復元に対応

**訓練：**
定期的な復元訓練を実施し、"本番時に慌てない"運用体制を整える

**トラブル例：**
誰かが重要テーブルをDROPしたが、前日のバックアップとbinlogで数分前まで完全復元できた'''
        }
    ]
    
    return create_ppt_from_content(
        slides_content,
        'pptx/バックアップとリカバリ～データベース安全管理の基本～.pptx'
    )

if __name__ == "__main__":
    try:
        print("🚀 バックアップとリカバリPPT生成中...")
        output_file = create_backup_recovery_ppt()
        print(f"✅ PPT生成完了: {output_file}")
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc() 