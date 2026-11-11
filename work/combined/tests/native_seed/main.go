package main
import (
 "fmt"
 "io"
 "os"
 "path/filepath"
 "github.com/anacrolix/torrent"
 "github.com/anacrolix/torrent/metainfo"
 "github.com/anacrolix/torrent/storage"
)
func main() {
 mi,err:=metainfo.LoadFromFile(os.Args[1]); if err!=nil {panic(err)}
 cfg:=torrent.NewDefaultClientConfig()
 cfg.DataDir=filepath.Dir(os.Args[1]); cfg.DefaultStorage=&seedStore{root:cfg.DataDir}; cfg.ListenPort=18901
 cfg.ListenHost=func(string)string{return "127.0.0.1"}
 cfg.DisableIPv6=true; cfg.NoDHT=true; cfg.DisableTrackers=true; cfg.DisablePEX=true
 cfg.NoDefaultPortForwarding=true; cfg.Seed=true
 client,err:=torrent.NewClient(cfg);if err!=nil{panic(err)};defer client.Close()
 t,err:=client.AddTorrent(mi);if err!=nil{panic(err)}
 <-t.GotInfo();t.DownloadAll()
 fmt.Printf("CBR test peer ready: %s\n",mi.HashInfoBytes().HexString())
 select{}
}

type seedStore struct{root string}
func(s *seedStore)Close()error{return nil}
func(s *seedStore)OpenTorrent(info *metainfo.Info, hash metainfo.Hash)(storage.TorrentImpl,error){
 data,err:=os.ReadFile(filepath.Join(s.root,info.Name));return &seedTorrent{data},err
}
type seedTorrent struct{data []byte}
func(s *seedTorrent)Close()error{return nil}
func(s *seedTorrent)Piece(p metainfo.Piece)storage.PieceImpl{return &seedPiece{s.data[p.Offset():p.Offset()+p.Length()]}}
type seedPiece struct{data []byte}
func(s *seedPiece)ReadAt(p []byte, off int64)(int,error){n:=copy(p,s.data[off:]);if n<len(p){return n,io.EOF};return n,nil}
func(s *seedPiece)WriteAt(p []byte,off int64)(int,error){return copy(s.data[off:],p),nil}
func(s *seedPiece)MarkComplete()error{return nil}
func(s *seedPiece)MarkNotComplete()error{return nil}
func(s *seedPiece)Completion()storage.Completion{return storage.Completion{Complete:true,Ok:true}}