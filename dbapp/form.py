from django import  forms
from .models import NumberTable,KenName
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError

class NumberForm(forms.Form):  
    kanji = forms.CharField(label='地名',widget=forms.TextInput(attrs={'placeholder':'地名','list':'item'}))
    class_number= forms.IntegerField(label='区分番号',min_value=0,max_value=999,widget=forms.NumberInput(attrs={'placeholder':'分類番号※3桁まで'}))
    hira = forms.CharField(label='ひらがな',max_length=1,widget=forms.TextInput(attrs={'placeholder':'ひらがな区分','pattern': r'^[あ-ん]+$'}))
    assign_number = forms.IntegerField(label='指定番号',min_value=0,max_value=9999,widget=forms.NumberInput(attrs={'placeholder':'指定番号※4桁まで'}))

class TimeiForm(forms.ModelForm):
    class Meta:
        model = KenName
        fields = ('ken_name',)
        widgets = {
            'ken_name':forms.TextInput(attrs={'placeholder':'地名'})
        }

class SearchForm(forms.Form):
        keyword = forms.CharField(label='', max_length=50,required=False)