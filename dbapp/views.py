from django.shortcuts import render,redirect,get_object_or_404
from django.views.generic import ListView,UpdateView
from .models import NumberTable,KenName, CarnumberLog
from .form import NumberForm,TimeiForm,SearchForm
import psycopg2
from django import forms
from django.contrib import messages


# 登録ナンバーの一覧と新規登録
def MainView(request):
    form = NumberForm(request.POST)
    if request.method == 'POST':
        if form.is_valid():
            kanji = request.POST["kanji"]
            class_number = request.POST["class_number"]
            hira = request.POST["hira"]
            assign_number = request.POST["assign_number"]
            if hira == 'お' or hira == 'し' or hira == 'へ' or hira == 'ん':
                messages.add_message(request, messages.ERROR, "指定のひらがな「お、し、へ、ん」は使えません")
            # DB登録
            elif KenName.objects.filter(ken_name = kanji).exists():
                number = kanji+class_number+hira+assign_number
                if NumberTable.objects.filter(number=number).exists():
                    messages.add_message(request, messages.ERROR, "このナンバーは既に登録されています。")
                else:
                    data = NumberTable(number=number,kanji =kanji,class_number=class_number,assign_number=assign_number,hira=hira)
                    data.save()
                    messages.add_message(request, messages.SUCCESS, "データ保存しました。")
                    return redirect('number:main')
            else:
                messages.add_message(request, messages.ERROR, "登録されている地名ではありません。正しい地名を入力してください。")
    serchform = SearchForm(request.GET)
    if serchform.is_valid():
        keyword = serchform.cleaned_data['keyword']
        number_list = NumberTable.objects.filter(number__icontains = keyword)
    else:
        number_list = NumberTable.objects.all()
    context = {'number_list':number_list,
                'item':KenName.objects.values('ken_name'),
                'form':form,
                'serchform':serchform}
    return render(request,'number_list.html',context)

# 登録ナンバーの編集
def EditNumber(request, number):
    data = get_object_or_404(NumberTable, number = number)
    values = {'kanji':data.kanji,'class_number':data.class_number,'hira':data.hira,'assign_number':data.assign_number}
    if request.method == 'POST':
        form = NumberForm(request.POST or values)
        if form.is_valid():
            kanji = request.POST["kanji"]
            class_number = request.POST["class_number"]
            hira = request.POST["hira"]
            assign_number = request.POST["assign_number"]
            if hira == 'お' or hira == 'し' or hira == 'へ' or hira == 'ん':
                messages.add_message(request, messages.ERROR, "指定のひらがな「お、し、へ、ん」は使えません")
            # DB更新
            elif  KenName.objects.filter(ken_name= kanji).exists():
                try:
                    number = kanji+class_number+hira+assign_number
                    conn = psycopg2.connect(host='10.16.76.108',user='postgres',password='takaya',port='5432', database='car_number')    
                    cursor = conn.cursor()
                    sql = " update number_table set number= %s,kanji=%s,class_number=%s,hira=%s,assign_number=%s where number= %s"
                    cursor.execute(sql,(number,kanji,class_number,hira,assign_number,data.number))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    messages.add_message(request, messages.SUCCESS, "ナンバー更新完了")
                    return redirect('number:main')
                except:
                    messages.add_message(request, messages.ERROR, "このナンバーは既に登録されています。")
            else:
                messages.add_message(request, messages.ERROR, "登録されている地名ではありません。正しい地名を入力してください。")
                return redirect('number:edit',data.number)
    else:
        form = NumberForm(values)
    
    return render(request,'number_edit.html',{'form':form,'item':KenName.objects.values('ken_name')})

# 登録ナンバーの削除
def DeleteNumber(request, number):
    number = get_object_or_404(NumberTable, number=number)

    number.delete()
    return redirect('number:main')

# 地名マスタの一覧と新規登録
def LocalView(request):
    form = TimeiForm(request.POST)
    if request.method == 'POST' :
        if form.is_valid():
            form.save()
            messages.add_message(request, messages.SUCCESS, "登録完了")
            return redirect('number:timei') 
        else:
            messages.add_message(request, messages.ERROR, "この地名は既に登録されています。")
    serchform = SearchForm(request.GET)
    if serchform.is_valid():
        keyword = serchform.cleaned_data['keyword']
        timei_list = KenName.objects.filter(ken_name__icontains = keyword)
    else:
        timei_list = KenName.objects.all()
    context = {'form':form ,
               'timei_list':timei_list,
               'serchform':serchform}
    return render(request,'timei_list.html',context)

# 地名の編集
def EditTimei(request,timei):
    timei = get_object_or_404(KenName, ken_name=timei)
    name = timei.ken_name
    if request.method == 'POST':
        form = TimeiForm(request.POST, instance=timei)
        if form.is_valid():
            try:
                conn = psycopg2.connect(host='10.16.76.108',user='postgres',password='takaya',port='5432', database='car_number')    
                cursor = conn.cursor()
                sql = "update ken_name set ken_name= %s where ken_name= %s"
                cursor.execute(sql,(request.POST["ken_name"],name))
                conn.commit()
                cursor.close()
                conn.close()
                messages.add_message(request, messages.SUCCESS, "地名更新完了")
                return redirect('number:timei')
            except:
                messages.add_message(request, messages.ERROR, "この地名は既に登録されています。")
    else:
        form = TimeiForm(instance=timei)
    return render(request,'timei_edit.html',{'form':form})

# 地名の削除
def DeleteTimei(request,timei):
    timei  = get_object_or_404(KenName, ken_name=timei)
    if  NumberTable.objects.filter(kanji = timei.ken_name).exists():
        messages.add_message(request, messages.ERROR, "この地名がナンバーとして登録されているため削除できません。ナンバー管理画面を確認してください。")
        return redirect('number:timei')
    else:
        timei.delete()
    return redirect('number:timei')

def LogView(request):
    print ("hello")

    log_list = CarnumberLog.objects.all()
    context = {'log_list': log_list}

    return render(request,'log.html',context)

