import React from "react";
import { Tabs, Card, List } from "antd";
const { TabPane } = Tabs;

const ManualScreen = () => {
  return (
    <Tabs defaultActiveKey="1">
      <TabPane tab="PPTから写真生成画面" key="1">
         <Card title="画面機能">
          <List
            size="small"
            bordered
            dataSource={[
              "PPTから写真に生成して、写真一覧エリアに表示する。生成した写真についてはダウンロード、削除、黒枠追加の操作ができる。",
            ]}
            renderItem={(item) => <List.Item>{item}</List.Item>}
          />
        </Card>

        <Card title="操作手順">
          <List size="small" bordered>
            <List.Item>① 「PPTをアップロード」ボタンを押下して、ローカルからPPTファイルを選択して、PPTをアップロードする。（一つのファイルから複数のファイルまでアップロードできる）</List.Item>
            <List.Item>② PPT一覧エリアにアップロードされたPPTファイルの情報を表示する。</List.Item>
            <List.Item>③ PPT一覧エリアで「写真生成」ボタンを押下して、選択されているPPTが写真に変換して、写真一覧にすべての写真を表示する。</List.Item>
            <List.Item>④ PPT一覧エリアで「写真一覧」ボタンを押下して、写真一覧にすべての写真を表示する。</List.Item>
            <List.Item>⑤ PPT一覧エリアで「削除」ボタンを押下して、アップロードされたPPTファイルが削除される。</List.Item>
            <List.Item>⑥ 写真一覧エリアで「選択した写真をダウンロード」ボタンを押下して、写真がダウンロードされる。</List.Item>
            <List.Item>⑦ 写真一覧エリアで「全部ダウンロード」ボタンを押下して、すべての写真がダウンロードされる。</List.Item>
            <List.Item>⑧ 写真一覧エリアで「選択した写真を削除」ボタンを押下して、写真が削除される。</List.Item>
            <List.Item>⑨ 写真一覧エリアで「全ての写真を削除」ボタンを押下して、写真が削除される。</List.Item>
            <List.Item>⑩ 写真一覧エリアで「黒枠追加」ボタンを押下して、写真に黒枠が追加されて、写真一覧エリアの黒枠画像列に表示される。</List.Item>
          </List>
        </Card>
      </TabPane>

      <TabPane tab="テキスト音声変換画面" key="2">
      <Card title="画面機能">
          <List
            size="small"
            bordered
            dataSource={[
              "PPTから写真、テキスト、音声、字幕に生成する。",
            ]}
            renderItem={(item) => <List.Item>{item}</List.Item>}
          />
        </Card>

        <Card title="操作手順">
          <List size="small" bordered>
            <List.Item>① 「PPTをアップロード」ボタンを押下して、ローカルからPPTファイルを選択して、PPTをアップロードする。</List.Item>
            <List.Item>② PPT一覧エリアにアップロードされたPPTファイルの情報を表示する。</List.Item>
            <List.Item>③ PPT一覧エリアで「写真生成」ボタンを押下して、選択されているPPTが写真に変換して、写真一覧にすべての写真を表示する。</List.Item>
            <List.Item>④ フォルダ選択エリアで「converted_images のフォルダを選択」から生成された写真フォルダを選択する。</List.Item>
            <List.Item>⑤ 「このフォルダの全画像の原稿を生成」ボタンを押下して、選択されたフォルダの写真から原稿を生成する。</List.Item>
            <List.Item>⑥ 「notes_output のフォルダを選択」から生成された原稿フォルダを選択する。</List.Item>
            <List.Item>⑦ 原稿ファイルエリアで生成された原稿ファイルを確認する。</List.Item>
            <List.Item>⑧ TTS 設定エリアでSpeech Keyを入力し、音声生成設定で言語の種類（日本語男性音声、日本語女性音声、中国語女性音声）を選択する。</List.Item>
            <List.Item>⑨ 「音声生成」ボタンを押下して、選択された原稿から音声と字幕を生成する。</List.Item>
            <List.Item>⑩ 音声ファイルエリアで生成された音声ファイルを確認し、再生できる。</List.Item>
            <List.Item>⑪ 字幕ファイルエリアで生成された字幕ファイルを確認し、ダウンロードできる。</List.Item>
            <List.Item>⑫ 「選択音声・字幕ダウンロード (ZIP)」ボタンを押下して、選択されたファイルをダウンロードする。</List.Item>
            <List.Item>⑬ 「break タグ確認」ボタンを押下して、字幕ファイルのbreakタグをチェックする。</List.Item>
            <List.Item>⑭ 「全削除」ボタンを押下して、生成されたファイルを削除する。</List.Item>
          </List>
        </Card>
      </TabPane>

      <TabPane tab="動画変換画面" key="3">
          <Card title="画面機能">
          <List
            size="small"
            bordered
            dataSource={[
              "ビデオファイルをアップロードした後、トランスコード処理を行って、新しいファイルに生成する。",
            ]}
            renderItem={(item) => <List.Item>{item}</List.Item>}
          />
        </Card>

        <Card title="操作手順">
          <List size="small" bordered>
            <List.Item>① タスク名称を入力して、「動画アップロード」ボタンを押下して、ビデオファイルをアップロードする。</List.Item>
            <List.Item>② 「元ファイルリスト」一覧にアップロードされたビデオ情報が表示される。</List.Item>
            <List.Item>③ 「変換開始」ボタンを押下して、「変換進度」エリアでステータスが表示される。</List.Item>
            <List.Item>④ 「変換済みファイルリスト」エリアでトランスコードされたビデオファイル情報が表示される。</List.Item>
            <List.Item>⑤ 「変換済みファイルリスト」エリアでトランスコードされたビデオファイルを選択して、「変換済みダウンロード」ボタンを押下して、トランスコードされたビデオファイルをダウンロードする。</List.Item>
            <List.Item>⑥ 「変換フォルダ表示」ボタンを押下して、トランスコードされたビデオファイルリストの情報を表示する。</List.Item>
            <List.Item>⑦ 「タスクビューに戻る」ボタンを押下して、メイン画面に戻る。</List.Item>          
          </List>
        </Card>
      </TabPane>
    </Tabs>
  );
};

export default ManualScreen;
