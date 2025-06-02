import React from "react";
import { Tabs, Card, List } from "antd";
const { TabPane } = Tabs;

const ManualScreen = () => {
  const renderItemWithImage = (text, imageName) => (
    <List.Item>
      {text}
      <div style={{ marginTop: 8 }}>
        <img
          src={`/images/${imageName}`}
          alt="操作手順の画像"
          style={{ width: "300px", height: "auto", marginTop: 8 }}
        />
      </div>
    </List.Item>
  );
  return (
    <Tabs defaultActiveKey="1">
      <TabPane tab="PDFから写真生成画面" key="1">
         <Card title="画面機能">
          <List
            size="small"
            bordered
            dataSource={[
              "PDFから写真に生成して、写真一覧エリアに表示する。生成した写真についてはダウンロード、削除、黒枠追加の操作ができる。",
            ]}
            renderItem={(item) => <List.Item>{item}</List.Item>}
          />
        </Card>

        <Card title="操作手順">
          <List size="small" bordered>
            {renderItemWithImage("① 「PDFをアップロード」ボタンを押下して、ローカルからPDFファイルを選択して、PDFをアップロードする。（一つのファイルから複数のファイルまでアップロードできる）", "pdfupload.png")}
            {renderItemWithImage("② PDF一覧エリアにアップロードされたPDFファイルの情報を表示する。", "pdflist.png")}
            {renderItemWithImage("③ PDF一覧エリアで「写真生成」ボタンを押下して、選択されているPDFが写真に変換して、写真一覧にすべての写真を表示する。", "pictureconversion.png")}
            {renderItemWithImage("④ PDF一覧エリアで「写真一覧」ボタンを押下して、写真一覧にすべての写真を表示する。", "pictureconversion.png")}
            {renderItemWithImage("⑤ PDF一覧エリアで「削除」ボタンを押下して、アップロードされたPDFファイルが削除される。", "pictureconversion.png")}
            {renderItemWithImage("⑥ 写真一覧エリアで「選択した写真をダウンロード」ボタンを押下して、写真がダウンロードされる。", "picturechoose.png")}
            {renderItemWithImage("⑦ 写真一覧エリアで「全部ダウンロード」ボタンを押下して、すべての写真がダウンロードされる。", "picturelist.png")}
            {renderItemWithImage("⑧ 写真一覧エリアで「選択した写真を削除」ボタンを押下して、写真が削除される。", "picturechoose.png")}
            {renderItemWithImage("⑨ 写真一覧エリアで「全ての写真を削除」ボタンを押下して、写真が削除される。", "picturelist.png")}
            {renderItemWithImage("⑩ 写真一覧エリアで「黒枠追加」ボタンを押下して、写真に黒枠が追加されて、写真一覧エリアの黒枠画像列に表示される。", "picturelist.png")}
          </List>
        </Card>
      </TabPane>

      <TabPane tab="文本转音频画面" key="2">
      <Card title="画面機能">
          <List
            size="small"
            bordered
            dataSource={[
              "写真からテキスト、音声、字幕に生成する。",
            ]}
            renderItem={(item) => <List.Item>{item}</List.Item>}
          />
        </Card>

        <Card title="操作手順">
          <List size="small" bordered>
            {renderItemWithImage("① 「PDFから写真生成画面」から生成した黒枠写真をタスクIDとして渡されて、「タスクIDプールダウン」から選択できる。", "ttstaskid.png")}
            {renderItemWithImage("② タスクIDを選択して「图片生成文稿」エリアに黒枠写真を表示する。", "ttspicture.png")}
            {renderItemWithImage("③ 「删除任务」ボタンを押下して、選択されたタスクが削除される。", "ttstaskiddelete.png")}
            {renderItemWithImage("④ TTS 设置エリアでキーを指定して、生成した音声に対して男性の声と女性の声のどちらかを選択ができる。", "ttsspeechkey.png")}
            {renderItemWithImage("⑤ 图片生成文稿エリアでApiKeyとPromptを入力して、黒枠写真を選択して、「生成选中」ボタンを押下して、文稿文件エリアに生成したテキストファイルが表示される。", "ttstext.png")}
            {renderItemWithImage("⑥ 图片生成文稿エリアで「全选所有文稿」ボタンを押下して、文稿文件エリアに生成したテキストファイルがチェックされる。", "ttstextcheck.png")}
            {renderItemWithImage("⑦ 图片生成文稿エリアで「全选所有音频和字幕」ボタンを押下して、音声ファイルと字幕ファイルがチェックされる。", "ttsvideojimakucheck.png")}
            {renderItemWithImage("⑧ 图片生成文稿エリアで「取消全选」ボタンを押下して、音声ファイルと字幕ファイルのチェックを外す。", "ttsvideojimakucheckdelete.png")}
            {renderItemWithImage("⑨ 图片生成文稿エリアで「生成选中文稿」ボタンを押下して、音声ファイルと字幕ファイルを生成する。", "ttsvideojimakumade.png")}
            {renderItemWithImage("⑩ 图片生成文稿エリアで「下载选中音频与字幕 (ZIP)」ボタンを押下して、選択されているファイルをダウンロードする。", "ttsdownload.png")}
            {renderItemWithImage("⑪ 图片生成文稿エリアで「检查 break 标签」ボタンを押下して、字幕ファイルをチェックして、breakが存在する場合はBreak 标签检查エリアで情報を表示する。", "ttsbreakcheck.png")}
            {renderItemWithImage("⑫ 图片生成文稿エリアで「删除所有」ボタンを押下して、生成した音声ファイルと字幕ファイルが削除される。", "ttsvideojimakudelete.png")}
            {renderItemWithImage("⑬ 音频文件エリアで「削除」ボタンを押下して、音声ファイルを削除する。", "ttsvideodelete.png")}
            {renderItemWithImage("⑭ 字幕文件で「削除」ボタンを押下して、字幕ファイルを削除する。", "ttsjimakudelete.png")}
          </List>
        </Card>
      </TabPane>

      <TabPane tab="视频转码画面" key="3">
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
            {renderItemWithImage("① タスク名称を入力して、「上传视频」ボタンを押下して、ビデオファイルをアップロードする。", "videoupload.png")}
            {renderItemWithImage("② 「原始文件列表」一覧にアップロードされたビデオ情報が表示される。", "videolist.png")}
            {renderItemWithImage("③ 「开始转码」ボタンを押下して、「转码进度」エリアでステータスが表示される。", "videotranscodingstatus.png")}
            {renderItemWithImage("④ 「已转码文件列表」エリアでトランスコードされたビデオファイル情報が表示される。", "videotranscodinglist.png")}
            {renderItemWithImage("⑤ 「已转码文件列表」エリアでトランスコードされたビデオファイルを選択して、「下载已转码」ボタンを押下して、トランスコードされたビデオファイルをダウンロードする。", "videotranscodingdownload.png")}
            {renderItemWithImage("⑥ 「查看转码文件夹」ボタンを押下して、トランスコードされたビデオファイルリストの情報を表示する。", "videoshowtranscodinglist.png")}
            {renderItemWithImage("⑦ 「返回任务视图」ボタンを押下して、メイン画面に戻る。", "videomain.png")}          
          </List>
        </Card>
      </TabPane>
    </Tabs>
  );
};

export default ManualScreen;
