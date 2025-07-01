# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from rest_framework.response import Response
from rest_framework import status, generics
from lms.djangoapps.common_models.models import UserDetails, RecommendedCourses, HMDCJourney, HMDCSuggetions
from common.djangoapps.student.models import UserProfile
from common.djangoapps.student.models import User
from .serializers import calculate_total_hours, extract_hours
from lms.djangoapps.common_models.serializers import UserDetailsSerializer, UserProfileSerializer,LeadSquareSignUpDataSerializer,UserProfileForLSSerializer, HMDCJourneySerializer
from openedx.core.djangoapps.catalog.utils import check_catalog_integration_and_get_user, get_catalog_api_client, get_catalog_api_base_url
from openedx.core.lib.edx_api_utils import get_api_data
from django.utils.safestring import mark_safe
from .serializers import CourseSerializer
from rest_framework.views import APIView
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview, PriceDisabledCourses
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from lms.djangoapps.course_category.models import NewCategoryMenu
from lms.djangoapps.edcast_api.models import CourseInformation
from collections import OrderedDict
from opaque_keys.edx.keys import CourseKey
from lms.djangoapps.subscription_package.utils import GetCourseDetails
from lms.djangoapps.ReactApi.apis.v1.courses.views import course_details
from datetime import datetime
from rest_framework.permissions import IsAuthenticated
from xmodule.modulestore.django import modulestore
from organizations.models import OrganizationCourse
from django.core.mail import EmailMultiAlternatives
from django.core.mail import send_mail
from django.core import mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.db.models import Q
import ast, requests, re

import logging
log = logging.getLogger(__name__)
log = logging.getLogger("edx.student")



class UserInterestsView(APIView):
    #in this class, creating  a POST request handler for user_details model whenever 
    #a user will post their details using the signup form.
    def post(self,request):
        leadsource = "Website_SignUp"
        try:
            user_id = (int)(request.data['user_id'])
        except (ValueError,AttributeError,KeyError) as error:
            return Response({"status":"failed", "Reason":"user_id is not provided"}, status=status.HTTP_400_BAD_REQUEST)
        user_details = UserDetails.objects.filter(user_id=user_id)
        if user_details.count()==0:            
            serializer = UserDetailsSerializer(data=request.data)            
            if serializer.is_valid():                
                instance = serializer.save()                
                user = instance.user_id                                                             
                data2 = LeadSquareSignUpDataSerializer(user).data   
                registered = "No"
                email_exists = User.objects.filter(email=data2['email']).exists()
                if email_exists:
                    registered = "Yes"                                  
                formatted_mobile_number=''
                if data2['profile']['phone_number']:
                    mobile_number = data2['profile']['phone_number']
                    formatted_mobile_number = mobile_number.replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
                else:
                    formatted_mobile_number=''
                full_name=''
                if data2['first_name'] and data2['last_name']:
                    full_name = data2['first_name'] +" "+ data2['last_name']
                else:
                    full_name=''
                news_lettersVal =  bool(data2['profile']['news_letters']) if 'news_letters' in data2['profile'] else False 
                country=data2['profile']['country'] if data2['profile']['country'] else ''                  
                level_of_education = data2['profile']['level_of_education'] if data2['profile']['level_of_education'] else ''
                if level_of_education == 'p':
                    level_of_education = 'Doctorate'
                elif level_of_education == 'm':
                    level_of_education = "Master's or professional degree"
                elif level_of_education == 'b':
                    level_of_education = "Bachelor's degree"
                elif level_of_education == 'a':
                    level_of_education = "Associate degree"
                elif level_of_education == 'hs':
                    level_of_education = "Secondary/high school"
                elif level_of_education == 'jhs':
                    level_of_education = "Junior secondary/junior high/middle school"
                elif level_of_education == 'el':
                    level_of_education = "Elementary/primary school"
                elif level_of_education == 'none':
                    level_of_education = "No formal education"
                elif level_of_education == 'other':
                    level_of_education = "Other education"
                year_of_birth= data2['profile']['year_of_birth'] if data2['profile']['year_of_birth'] else ''
                gender= data2['profile']['gender'] if data2['profile']['gender'] else '' 
                if gender == 'm':
                    gender = 'Male'
                elif gender == 'f':
                    gender = "Female"
                elif gender == 'o':
                    gender = "Other/Prefer Not to Say"
                interests = data2['details']['interests'] if data2['details']['interests'] else ''              
                work_status= data2['details']['work_status'] if data2['details']['work_status'] else ''
                work_experience= data2['details']['work_experience'] if data2['details']['work_experience'] else ''  
                date_str =data2['date_joined']
                # date_format = '%Y-%m-%dT%H:%M:%S.%fZ'
                # datetime_obj = datetime.strptime(date_str, date_format)        
                date_formats = ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%S%fZ']
                datetime_obj = None
                for date_format in date_formats:
                    try:
                        datetime_obj = datetime.strptime(date_str, date_format)
                        break
                    except ValueError:
                        pass            
                # Extract the date portion from the datetime object
                date_registered = str(datetime_obj.date())   
                time_registered = str(datetime_obj.strftime('%H:%M:%S'))                                   
                try:
                    if 'dev' not in request.META['HTTP_REFERER']:                        
                        data_to_upload = [
                        {
                            "Attribute": "FirstName",
                            "Value": full_name
                        },
                        {
                        "Attribute": "Phone",
                        "Value": formatted_mobile_number
                        },
                        {
                            "Attribute": "EmailAddress",
                            "Value": data2['email']
                        },
                        {
                        "Attribute": "mx_News_Letters",
                        "Value": news_lettersVal
                        },
                        {
                        "Attribute": "mx_Country",
                        "Value": country
                        },
                        {
                        "Attribute": "mx_Your_current_status",
                        "Value": work_status
                        },
                        {
                        "Attribute": "mx_Gender",
                        "Value": gender
                        },
                        {
                        "Attribute": "mx_Year_of_Birth",
                        "Value": year_of_birth
                        },
                        {
                        "Attribute": "mx_Level_of_Education",
                        "Value": level_of_education
                        },  
                        {
                        "Attribute": "mx_Which_future_skills_are_you_interested_in",
                        "Value": interests
                        },    
                        {
                        "Attribute": "mx_Work_Experience",
                        "Value": work_experience
                        },   
                        {
                            "Attribute": "mx_Date_Registered",
                            "Value": date_registered
                        },
                        {
                            "Attribute": "Source",
                            # "Value": "Website_SignUp",
                            "Value": leadsource
                        },
                            
                        {
                            "Attribute": "mx_Time_Registered",
                            "Value": time_registered
                        },       
                        {
                            "Attribute": "mx_Registered",
                            "Value": registered
                        },                                                                                             
                        ]
                        url = settings.LEADSQUARED_API_CAPTURE
                        r = requests.post(url, json = data_to_upload)                                                
                except Exception as e:
                    logging.info(e)                        
                return Response({"status": "success"}, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            serializer = UserDetailsSerializer(user_details[0], data=request.data)
            if serializer.is_valid():
                instance = serializer.save()                
                user = instance.user_id
                data2 = LeadSquareSignUpDataSerializer(user).data
                registered = "No"
                email_exists = User.objects.filter(email=data2['email']).exists()
                if email_exists:
                    registered = "Yes"                
                # if 'userinterests/?interested_in_job' in request.build_absolute_uri():                                             
                formatted_mobile_number=''
                if data2['profile']['phone_number']:
                    mobile_number = data2['profile']['phone_number']
                    formatted_mobile_number = mobile_number.replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
                else:
                    formatted_mobile_number=''
                full_name=''
                if data2['first_name'] and  data2['last_name']:
                    full_name = data2['first_name'] +" "+ data2['last_name']
                else:
                    full_name=''
                news_lettersVal = bool(data2['profile']['news_letters']) if 'news_letters' in data2['profile'] else False  
                country=data2['profile']['country'] if data2['profile']['country'] else ''                
                level_of_education = data2['profile']['level_of_education'] if data2['profile']['level_of_education'] else ''
                if level_of_education == 'p':
                    level_of_education = 'Doctorate'
                elif level_of_education == 'm':
                    level_of_education = "Master's or professional degree"
                elif level_of_education == 'b':
                    level_of_education = "Bachelor's degree"
                elif level_of_education == 'a':
                    level_of_education = "Associate degree"
                elif level_of_education == 'hs':
                    level_of_education = "Secondary/high school"
                elif level_of_education == 'jhs':
                    level_of_education = "Junior secondary/junior high/middle school"
                elif level_of_education == 'el':
                    level_of_education = "Elementary/primary school"
                elif level_of_education == 'none':
                    level_of_education = "No formal education"
                elif level_of_education == 'other':
                    level_of_education = "Other education"
                year_of_birth= data2['profile']['year_of_birth'] if data2['profile']['year_of_birth'] else ''
                gender= data2['profile']['gender'] if data2['profile']['gender'] else '' 
                if gender == 'm':
                    gender = 'Male'
                elif gender == 'f':
                    gender = "Female"
                elif gender == 'o':
                    gender = "Other/Prefer Not to Say"
                interests = data2['details']['interests'] if data2['details']['interests'] else ''              
                work_status= data2['details']['work_status'] if data2['details']['work_status'] else ''
                work_experience= data2['details']['work_experience'] if data2['details']['work_experience'] else ''
                date_str =data2['date_joined']
                # date_format = '%Y-%m-%dT%H:%M:%S.%fZ'                
                # datetime_obj = datetime.strptime(date_str, date_format)
                date_formats = ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%S%fZ']
                datetime_obj = None
                for date_format in date_formats:
                    try:
                        datetime_obj = datetime.strptime(date_str, date_format)
                        break
                    except ValueError:
                        pass
                date_registered = str(datetime_obj.date()) 
                time_registered = str(datetime_obj.strftime('%H:%M:%S'))                                                 
                try:
                    if 'dev' not in request.META['HTTP_REFERER']:                        
                        data_to_upload = [
                        {
                            "Attribute": "FirstName",
                            "Value": full_name
                        },
                        {
                        "Attribute": "Phone",
                        "Value": formatted_mobile_number
                        },
                        {
                            "Attribute": "EmailAddress",
                            "Value": data2['email']
                        },
                        {
                        "Attribute": "mx_News_Letters",
                        "Value": news_lettersVal
                        },
                        {
                        "Attribute": "mx_Country",
                        "Value": country
                        },
                        {
                        "Attribute": "mx_Your_current_status",
                        "Value": work_status
                        },
                        {
                        "Attribute": "mx_Gender",
                        "Value": gender
                        },
                        {
                        "Attribute": "mx_Year_of_Birth",
                        "Value": year_of_birth
                        },
                        {
                        "Attribute": "mx_Level_of_Education",
                        "Value": level_of_education
                        },  
                        {
                        "Attribute": "mx_Which_future_skills_are_you_interested_in",
                        "Value": interests
                        },    
                        {
                        "Attribute": "mx_Work_Experience",
                        "Value": work_experience
                        },   
                        {
                            "Attribute": "mx_Date_Registered",
                            "Value": date_registered
                        },   
                        {
                            "Attribute": "mx_Registered",
                            "Value": registered
                        },    
                        # {
                        #     "Attribute": "mx_Time_Registered",
                        #     "Value": time_registered
                        # },                                                                        
                        ]
                    url = settings.LEADSQUARED_API_CAPTURE
                    r = requests.post(url, json = data_to_upload)                                        
                except Exception as e:
                    logging.info("testing... leadsquare")                       
                return Response({"status": "success"}, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class UserUpdateView(APIView):
    def get(self, request):
        try:
            user_id = request.user.id
        except (ValueError, AttributeError, KeyError) as error:
            return Response({"status": "failed", "Reason": "user_id is not provided"}, status=status.HTTP_400_BAD_REQUEST)
        user_profile = UserProfile.objects.filter(user_id=user_id)
        user_details = UserDetails.objects.filter(user_id=user_id)
        if user_profile.count() == 0 or user_details.count() == 0:
            return Response(status=status.HTTP_404_NOT_FOUND)
        user_profile_data = UserProfileSerializer(user_profile[0]).data
        user_details_data = UserDetailsSerializer(user_details[0]).data
        combined_data = {
            "user_profile": user_profile_data,
            "user_details": user_details_data
        }
        return Response(combined_data, status=status.HTTP_200_OK)
class UserProfileView(APIView):
    #in this class, creating  a POST request handler for user_profile model whenever 
    #a user will post their details using the signup form.
    def post(self,request):
        try:
            user_id = (int)(request.data['user_id'])
        except (ValueError,AttributeError,KeyError) as error:
            return Response({"status":"failed", "Reason":"user_id is not provided"}, status=status.HTTP_400_BAD_REQUEST)
        user_profile = UserProfile.objects.filter(user_id=user_id)
        if user_profile.count()==0:
            return Response(status=status.HTTP_404_NOT_FOUND)        
        serializer = UserProfileSerializer(user_profile[0], data=request.data)        
        if serializer.is_valid():
            # serializer.save()                 
            instance = serializer.save()
            user_instance = instance.user  # Get the related User instance
            data2 = LeadSquareSignUpDataSerializer(user_instance).data   
            registered = "No"
            email_exists = User.objects.filter(email=data2['email']).exists()
            if email_exists:
                registered = "Yes"         
            formatted_mobile_number=''
            if data2['profile']['phone_number']:
                mobile_number = data2['profile']['phone_number']
                formatted_mobile_number = mobile_number.replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
            else:
                formatted_mobile_number=''
            full_name=''
            if data2['first_name'] and  data2['last_name']:
                full_name = data2['first_name'] +" "+ data2['last_name']
            else:
                full_name=''
            # news_lettersVal = data2['profile']['news_letters'] if data2['profile']['news_letters'] else '' 
            news_lettersVal =  bool(data2['profile']['news_letters']) if 'news_letters' in data2['profile'] else False
            country=data2['profile']['country'] if data2['profile']['country'] else ''             
            level_of_education = data2['profile']['level_of_education'] if data2['profile']['level_of_education'] else ''
            if level_of_education == 'p':
                level_of_education = 'Doctorate'
            elif level_of_education == 'm':
                level_of_education = "Master's or professional degree"
            elif level_of_education == 'b':
                level_of_education = "Bachelor's degree"
            elif level_of_education == 'a':
                level_of_education = "Associate degree"
            elif level_of_education == 'hs':
                level_of_education = "Secondary/high school"
            elif level_of_education == 'jhs':
                level_of_education = "Junior secondary/junior high/middle school"
            elif level_of_education == 'el':
                level_of_education = "Elementary/primary school"
            elif level_of_education == 'none':
                level_of_education = "No formal education"
            elif level_of_education == 'other':
                level_of_education = "Other education"
            year_of_birth= data2['profile']['year_of_birth'] if data2['profile']['year_of_birth'] else ''
            gender= data2['profile']['gender'] if data2['profile']['gender'] else '' 
            if gender == 'm':
                gender = 'Male'
            elif gender == 'f':
                gender = "Female"
            elif gender == 'o':
                gender = "Other/Prefer Not to Say"
            interests = data2['details']['interests'] if data2['details']['interests'] else ''              
            work_status= data2['details']['work_status'] if data2['details']['work_status'] else ''
            work_experience= data2['details']['work_experience'] if data2['details']['work_experience'] else ''                                   
            try:
                if 'dev' not in request.META['HTTP_REFERER']:                    
                    data_to_upload = [
                    {
                        "Attribute": "FirstName",
                        "Value": full_name
                    },
                    {
                    "Attribute": "Phone",
                    "Value": formatted_mobile_number
                    },
                    {
                        "Attribute": "EmailAddress",
                        "Value": data2['email']
                    },
                    {
                    "Attribute": "mx_News_Letters",
                    "Value": news_lettersVal
                    },
                    {
                    "Attribute": "mx_Country",
                    "Value": country
                    },
                    {
                    "Attribute": "mx_Your_current_status",
                    "Value": work_status
                    },
                    {
                    "Attribute": "mx_Gender",
                    "Value": gender
                    },
                    {
                    "Attribute": "mx_Year_of_Birth",
                    "Value": year_of_birth
                    },
                    {
                    "Attribute": "mx_Level_of_Education",
                    "Value": level_of_education
                    },  
                    {
                    "Attribute": "mx_Which_future_skills_are_you_interested_in",
                    "Value": interests
                    },    
                    {
                    "Attribute": "mx_Work_Experience",
                    "Value": work_experience
                    },  
                    {
                        "Attribute": "mx_Registered",
                        "Value": registered
                    },                                                                            
                    ]
                    url = settings.LEADSQUARED_API_CAPTURE
                    r = requests.post(url, json = data_to_upload)                    
            except Exception as e:
                logging.info(e)                      
            return Response({"status": "success"}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RecommendedCourses_APIView(APIView):
    def package_handling(self, course_id, datas):
        usd = []
        inr = []
        for data in datas[str(course_id)]['packages']:
            for key, value in data.items():
                if key.lower() == 'usd':
                    usd.append({
                        'price_original_USD': "$" + "{:,}".format(int(round(value['cost_price']))) if value['cost_price'] else 0,
                        'price_USD': "$" + "{:,}".format(int(round(value['price']))),
                        'package_sku': value['partner_sku'],
                        'package_name': value['package_name'],
                        'access_duration' : value['access_duration']
                    })
                else:
                    inr.append({
                        'price_original_INR': "₹" + "{:,}".format(int(round(value['cost_price'] / 1.18))) if value['cost_price'] else 0,
                        'price_INR': "₹" + "{:,}".format(int(round(value['price'] / 1.18))),
                        'package_sku': value['partner_sku'],
                        'package_name': value['package_name'],
                        'access_duration' : value['access_duration']
                    })
        packages = [usd, inr] 
        return packages
    def datetime_handling(self, date):
        try:
            date = date.strftime("%b %d, %Y")
        except:
            pass
        return date
    def handling(self, request, courses, recommended, data):
        temp_data = GetCourseDetails(request, courses)
        datas = temp_data.GetCoursesAll()
        for i in recommended:
            course_key = CourseKey.from_string(i.course_id)
            course_detail = courses.filter(id=course_key)
            display_name = course_detail[0].display_name
            course_org = course_detail[0].org
            try:
                course_org = OrganizationCourse.objects.get(course_id=str(i.course_id)).organization.name
            except:
                pass
            course_image_url = course_detail[0].course_image_url
            self_paced = course_detail[0].self_paced
            enrollment_start = self.datetime_handling(course_detail[0].enrollment_start)
            enrollment_end = self.datetime_handling(course_detail[0].enrollment_end)
            start = self.datetime_handling(course_detail[0].start)
            end = self.datetime_handling(course_detail[0].end)
            listed_as_program = datas[str(i.course_id)]['listed_as_program']
            course_id = str(i.course_id)
            price_original_INR = None 
            price_original_USD = None 
            sku_inr = None
            sku_usd = None
            single_price = False
            packages = []
            price_INR = None
            price_USD = None
            blended = False
            mentored = False
            course_level = None
            course_temp = modulestore().get_course(course_key, depth=None)
            if course_temp:
                mentored = course_temp.other_course_settings.get('Mentored', False)
                course_level = course_temp.other_course_settings.get('Course Level', None)
                blended = course_temp.other_course_settings.get('Blended', False)
                try:
                    if(blended.upper() == "YES"):
                            blended = True
                except:
                    pass
            if 'single_price' in datas[str(course_id)]:
                single_price = True
                try:
                    for key, value in datas[str(course_id)]['single_price_details'].items():
                        if key.lower() == 'usd':
                            price_original_USD = "$" + "{:,}".format(int(round(value['cost_price']))) if value['cost_price'] else 0
                            price_USD = "$" + "{:,}".format(int(round(value['price'])))
                            sku_usd = value['sku']
                        else:
                            price_original_INR = "₹" + "{:,}".format(int(round(value['cost_price'] / 1.18))) if value['cost_price'] else 0
                            price_INR = "₹" + "{:,}".format(int(round(value['price'] / 1.18)))
                            sku_inr = value['sku']
                except:
                    pass
            if "single_price" not in datas[str(course_id)]:
                packages = self.package_handling(course_id, datas)
            data[i.course_id] = {
                    "blended": blended,
                    "course_image_url": course_image_url,
                    "course_level": course_level,
                    "id": i.course_id,
                    "display_name": display_name,
                    "end": end,
                    "enrollment_start": enrollment_start,
                    "enrollment_end": enrollment_end,
                    "mentored": mentored,
                    "org": course_org,
                    "self_paced": self_paced,
                    "listed_as_program": listed_as_program,
                    "packages": packages,
                    "price_INR": price_INR,
                    "price_USD": price_USD,
                    "start": start
                }
        # Alphabetical Handling
        res = []
        keys = ["blended", "course_image_url", "course_level", "display_name", "end", "enrollment_start", "enrollment_end", "id", "mentored", "org", "listed_as_program", "self_paced", "start", "price_INR", "price_USD", "packages"]
        for i in data.values():
            try:
                res.append({
                    "blended": i["blended"],
                    "course_image_url": i["course_image_url"],
                    "course_level": i["course_level"],
                    "display_name": i["display_name"],
                    "end": i["end"],
                    "enrollment_start": i["enrollment_start"],
                    "enrollment_end": i["enrollment_end"],
                    "id": i["id"],
                    "mentored": i["mentored"],
                    "org": i["org"],
                    "listed_as_program": i["listed_as_program"],
                    "self_paced": i["self_paced"],
                    "packages": i["packages"],
                    "price_INR": i["price_INR"],
                    "price_USD": i["price_USD"],
                    "start": i["start"]
                })
            except:
                pass
        sorted_results = []
        for result in res:
            sorted_result = OrderedDict()
            for key in keys:
                if key in result:
                    sorted_result[key] = result[key]
            sorted_results.append(sorted_result)
        return sorted_results
    def get(self, request):
        courses = CourseOverview.objects.all()
        recommended = RecommendedCourses.objects.all()
        data = {}
        data = self.handling(request, courses, recommended, data)
        return Response({"length": len(data), "results": data}, status=status.HTTP_200_OK)


def simplified_courses(self, request):
    mode = request.query_params.get('learning_style', None)
    cat = request.data.get('category', None)
    level = request.data.get('skill_level', None)
    focus = request.data.get('skill_focus', None)
    course_duration = request.data.get('course_duration', None)
    if level == "I don't know. I need help":
        level = None
    if mode == "No strong preference":
        mode = None
    if course_duration == "New Adventurer":
        course_duration = None
    all_courses = []
    courses = CourseOverview.objects.filter(invitation_only=False).order_by('-end')
    
    if cat:
        if focus in ["Human Skills", "Combination of both"]:
            all_category_courses = NewCategoryMenu.objects.filter(Q(name=cat) | Q(name="Human Skills")).values_list('course_list', flat=True)
        else:
            all_category_courses = NewCategoryMenu.objects.filter(name=cat).values_list('course_list', flat=True)
        all_category_courses = [i.split('\r\n') for i in all_category_courses]
        all_category_courses = [CourseKey.from_string(course_id) for course_list in all_category_courses for course_id in course_list]
        courses = CourseOverview.objects.filter(id__in=all_category_courses).order_by('-end')
    
    pricedisabledCourses = PriceDisabledCourses.objects.all()
    temp_courses_price_enabled = []
    for course in pricedisabledCourses:
        temp_courses_price_enabled.append(CourseKey.from_string(str(course.course_id)))
    courses = courses.exclude(id__in=temp_courses_price_enabled)
    
    for course in courses:
        all_courses.append(str(course.id))
    
    courses = course_details(self.request, courses, all_courses)
    
    if mode:
        temp_courses_blended = []
        temp_courses_instructor = []
        temp_courses_self = []
        for m in ','.join(mode).split(','):
            for course in courses:
                if "self_paced" in m:
                    if hasattr(course, 'blended'):
                        if course.blended == False and course.self_paced == True:
                            temp_courses_self.append(course)
                    else:
                        if course.self_paced == True:
                            temp_courses_self.append(course)
                elif "blended" in m:
                    if hasattr(course, 'blended'):
                        if course.blended:
                            temp_courses_blended.append(course)
                elif "instructor_led" in m:
                    if hasattr(course, 'blended'):
                        if course.blended == False and course.self_paced == False:
                            temp_courses_instructor.append(course)
                    else:
                        if course.self_paced == False:
                            temp_courses_instructor.append(course)
        courses = temp_courses_blended + temp_courses_instructor + temp_courses_self
    
    if level:
        course_levels = []
        for course in courses:
            try:
                if course.course_level and level.lower().strip() == (course.course_level).lower().strip():
                    course_levels.append(course)
            except:
                pass
        courses = course_levels
    serializer = CourseSerializer(courses, many=True)
    serialized_data = serializer.data
    
    if course_duration:
        if course_duration == "Focused Explorer":
            serialized_data = [course for course in serialized_data if 0 <= course['effort_hours'] <= 25]
        elif course_duration == "Steady Voyager":
            serialized_data = [course for course in serialized_data if 26 <= course['effort_hours'] <= 70]
        elif course_duration == "All-round Seeker":
            serialized_data = [course for course in serialized_data if course['effort_hours'] >= 71]
    return serialized_data



def simplified_programs(self, request, uuid=None):
    filter_category = request.data.get('category', None)
    skill_level = request.data.get('skill_level', None)
    learning_type = request.data.get('learning_style', None)
    course_duration = request.data.get('course_duration', None)
    if skill_level == "I don't know. I need help":
        skill_level = None
    if learning_type == "No strong preference":
        learning_type = None
    if course_duration == "New Adventurer":
        course_duration = None
    programs = []
    user, catalog_integration = check_catalog_integration_and_get_user(error_message_field='Course runs')
    base_api_url = get_catalog_api_base_url()
    if user:
        api = get_catalog_api_client(user)
        endpoint = 'programs/' + (uuid + '/' if uuid else '')
        programs = get_api_data(catalog_integration, endpoint, base_api_url=base_api_url, api_client=api)
        programs = [programs] if uuid else programs

    all_programs = []
    sorted_programs = sorted(programs, key=lambda x: x['marketing_slug'], reverse=True)
    for data in sorted_programs:
        if not data['hidden'] and data['status'] != 'unpublished':
            single_program = False
            slug = data['marketing_slug']
            try:
                org = OrganizationCourse.objects.get(course_id=slug).organization.name
                org_image = OrganizationCourse.objects.get(course_id=slug).organization.logo.url
            except OrganizationCourse.DoesNotExist:
                org = None
                org_image = None
            categories = []
            category = NewCategoryMenu.objects.filter(program_list__contains=slug, name=filter_category, name__isnull=False)
            for cat in category:
                if cat.name != "":
                    categories.append(cat.name)
            try:
                details = ast.literal_eval(data['credit_redemption_overview'].encode('ascii', 'ignore').decode('ascii'))
                duration = details['Duration']
                duration_hrs = calculate_total_hours(duration)
                course_level = details['course_level']
                course_type = details['course_type']
                mentored = details['mentored'] if 'mentored' in details else None
            except Exception as e:
                duration = None
                duration_hrs = None
                course_level = None
                course_type = None
                mentored = None

            if categories != [] and course_level == skill_level  and (course_type == learning_type or mentored == learning_type):
                if course_duration == 'Focused Explorer' and duration_hrs is not None and duration_hrs <= 25:
                    all_programs.append({
                        'slug': data['marketing_slug'],
                        'display_name': data['title'],
                        'status': data['status'],
                        'type': data['type'],
                        'org': org,
                        'subtitle': mark_safe(data['subtitle']),
                        'duration': duration_hrs,
                        'category': categories,
                        'course_level': course_level,
                        'course_type': course_type,
                        'mentored': mentored,})
                elif course_duration == 'Steady Voyager' and duration_hrs is not None and 26 <= duration_hrs <= 70:
                    all_programs.append({
                        'slug': data['marketing_slug'],
                        'display_name': data['title'],
                        'status': data['status'],
                        'type': data['type'],
                        'org': org,
                        'subtitle': mark_safe(data['subtitle']),
                        'duration': duration_hrs,
                        'category': categories,
                        'course_level': course_level,
                        'course_type': course_type,
                        'mentored': mentored,})
                elif course_duration == 'All-round Seeker' and duration_hrs is not None and duration_hrs > 70:
                    all_programs.append({
                        'slug': data['marketing_slug'],
                        'display_name': data['title'],
                        'status': data['status'],
                        'type': data['type'],
                        'org': org,
                        'subtitle': mark_safe(data['subtitle']),
                        'duration': duration_hrs,
                        'category': categories,
                        'course_level': course_level,
                        'course_type': course_type,
                        'mentored': mentored,})
                else:
                    all_programs.append({
                        'slug': data['marketing_slug'],
                        'display_name': data['title'],
                        'status': data['status'],
                        'type': data['type'],
                        'org': org,
                        'subtitle': mark_safe(data['subtitle']),
                        'duration': duration_hrs,
                        'category': categories,
                        'course_level': course_level,
                        'course_type': course_type,
                        'mentored': mentored,})

    return all_programs






class HMDCJourneyView(APIView):
    def remove_html_tags_and_extract(self, description):
        pattern = re.compile(r'<.*?>')
        clean_description = pattern.sub('', description)
        parts = clean_description.split('.')
        result = '.'.join(parts[:2])
        return result

    def send_email_with_suggetions(self,data,record):
        frontend_url = configuration_helpers.get_value('FRONTEND_URL')
        programs = simplified_programs(self, self.request)
        # logging.info(self.request.__dict__)
        courses = simplified_courses(self, self.request)
        # logging.info(self.request.__dict__)
        courses_and_programs_list = []

        for program in programs:
            programs_details = {
                'id': program["slug"],
                'site': frontend_url,
                'display_name': program["display_name"],
                'short_description': self.remove_html_tags_and_extract(program["subtitle"])}
            courses_and_programs_list.append(programs_details)
        for course in courses:
            courses_details = {
                'id': 'courses/'+course["id"],
                'site': frontend_url,
                'display_name': course["display_name"],
                'short_description': self.remove_html_tags_and_extract(course["short_description"])}
            courses_and_programs_list.append(courses_details)

        limited_records = courses_and_programs_list[:4]
        context = {'courses_and_programs_list': limited_records,'fe_site':frontend_url}
        # logging.info(context)
        if limited_records:
            html_message = render_to_string('emails/html_emails/hmdc_email1.html', context)
            record.checked = True


        elif not limited_records:
            additional_courses = []
            category = data.get('category')
            for suggestion in HMDCSuggetions.objects.all():
                if suggestion.category == category:
                    additional_courses.append({
                        'id': suggestion.slug,
                        'display_name': suggestion.course_name,
                        'short_description': suggestion.description})
            if not additional_courses:
                for suggestion in HMDCSuggetions.objects.filter(category='Other'):
                    additional_courses.append({
                        'id': suggestion.slug,
                        'display_name': suggestion.course_name,
                        'short_description': suggestion.description})
            # Additional check for frontend_url and category 'Big Data'
            if frontend_url in ["https://dev.spinup.tech", "https://qa.spinup.tech", "https://skillup.online"]:
                big_data_suggestions = HMDCSuggetions.objects.filter(Q(category='Big Data') | Q(category="Data Analytics")).order_by('-id')[:3]
                additional_courses.extend(big_data_suggestions)
                additional_courses = additional_courses[1:4]
            context['courses_and_programs_list'] = additional_courses
            html_message = render_to_string('emails/html_emails/hmdc_email2.html', context)
        else:
            html_message = render_to_string('emails/html_emails/hmdc_email2.html', context)

        plain_message = strip_tags(html_message)
        email = EmailMultiAlternatives(
            subject="Course Recommendations to Boost Your Career | SkillUp Online",
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[data['email']],
        )
        email.attach_alternative(html_message, 'text/html')
        email.send(fail_silently=False)
        record.save()

    def post(self, request):
        record_id = request.data.get('id')
        record = None
        if record_id:
            # Update existing record
            try:
                record = HMDCJourney.objects.get(id=record_id)
                serializer = HMDCJourneySerializer(record, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    data = serializer.data
                    leadsource = "HMDC_Website"      
                    self.send_email_with_suggetions(data, record)
                    checked = "True" if record.checked else "False"         
                    try:                       
                        data_to_upload = [
                            {"Attribute": "FirstName", "Value": data["full_name"]},
                            {"Attribute": "Phone", "Value": data["mobile_number"]},
                            {"Attribute": "EmailAddress", "Value": data["email"]},
                            {"Attribute": "Company", "Value": data["organization"]},
                            {"Attribute": "mx_CareerGoals", "Value": data["career_goals"]},
                            {"Attribute": "mx_CurrentField", "Value": data["current_field"]},
                            {"Attribute": "mx_Category", "Value": data["category"]},
                            {"Attribute": "mx_SkillLevel", "Value": data["skill_level"]},
                            {"Attribute": "mx_SkillFocus", "Value": data["skill_focus"]},
                            {"Attribute": "mx_LearningStyle", "Value": data["learning_style"]},
                            {"Attribute": "mx_CourseDuration", "Value": data["course_duration"]},
                            {"Attribute": "mx_CodingInterest", "Value": data["coding_interest"]},
                            {"Attribute": "mx_PerfectMatch", "Value": checked},
                            {"Attribute": "Source", "Value": leadsource},                  
                        ]
                        url = settings.LEADSQUARED_API_CAPTURE
                        r = requests.post(url, json=data_to_upload)
                    except Exception as e:                        
                        logging.info(e)
                    return Response(data, status=status.HTTP_200_OK)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            except HMDCJourney.DoesNotExist:
                return Response({'error': f"Record with ID {record_id} does not exist."}, status=status.HTTP_404_NOT_FOUND)
        else:
            serializer = HMDCJourneySerializer(data=request.data)
            if serializer.is_valid():
                # serializer.save()
                record = serializer.save() 
                data = serializer.data
                leadsource = "HMDC_Website" 
                self.send_email_with_suggetions(data, record)
                checked = "True" if record.checked else "False" 
                try:
                    data_to_upload = [
                        {"Attribute": "FirstName", "Value": data["full_name"]},
                        {"Attribute": "Phone", "Value": data["mobile_number"]},
                        {"Attribute": "EmailAddress", "Value": data["email"]},
                        {"Attribute": "Company", "Value": data["organization"]},
                        {"Attribute": "mx_CareerGoals", "Value": data["career_goals"]},
                        {"Attribute": "mx_CurrentField", "Value": data["current_field"]},
                        {"Attribute": "mx_Category", "Value": data["category"]},
                        {"Attribute": "mx_SkillLevel", "Value": data["skill_level"]},
                        {"Attribute": "mx_SkillFocus", "Value": data["skill_focus"]},
                        {"Attribute": "mx_LearningStyle", "Value": data["learning_style"]},
                        {"Attribute": "mx_CourseDuration", "Value": data["course_duration"]},
                        {"Attribute": "mx_CodingInterest", "Value": data["coding_interest"]},
                        {"Attribute": "mx_PerfectMatch", "Value": checked},
                        {"Attribute": "Source", "Value": leadsource},                  
                    ]
                    url = settings.LEADSQUARED_API_CAPTURE
                    r = requests.post(url, json=data_to_upload)
                except Exception as e:
                    logging.info(e)
                return Response(data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


from django.http import JsonResponse
from django.contrib.auth.models import User
from common.djangoapps.student.models import UserProfile
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from rest_framework.decorators import api_view
from rest_framework import status
from openedx.core.djangoapps.catalog.utils import check_catalog_integration_and_get_user, get_catalog_api_client, get_catalog_api_base_url

@api_view(['POST'])
def get_user_and_course_info(request): 
    email = request.data.get('email')
    course_id = request.data.get('course_id')
    program_uuid = request.data.get('program_uuid')
    
    if not email:
        return JsonResponse(
            {"error": "Email is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Initialize variables
    phone_number = None
    course_start_date = None
    program_start_date = None

    try:
        # Fetch user and profile
        user = User.objects.get(email=email)
        profile = UserProfile.objects.get(user=user)
        phone_number = profile.phone_number
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
    except UserProfile.DoesNotExist:
        pass  # phone_number remains None

    # Handle course info if course_id provided
    if course_id:
        try:
            course = CourseOverview.objects.get(id=course_id)
            if course.start:
                course_start_date = course.start.isoformat()
        except CourseOverview.DoesNotExist:
            pass  # course_start_date remains None

    # Handle program info if program_uuid provided
    if program_uuid:
        try:
            api_url = f"{settings.LMS_ROOT_URL}/sko/v1/program/{program_uuid}/"
            response = requests.get(api_url)
            response.raise_for_status()
            program_data = response.json()

            # Extract start date from response
            if isinstance(program_data, list) and program_data:
                program_start_date = program_data[0].get('start')
            elif isinstance(program_data, dict):
                program_start_date = program_data.get('start')
            
            # If the date is already in string format, keep it as is
            # If it's a date object, convert to ISO format
            if program_start_date and hasattr(program_start_date, 'isoformat'):
                program_start_date = program_start_date.isoformat()
                
        except Exception as e:
            logging.error(f"Error fetching program details: {e}")
            # program_start_date remains None

    # Prepare response data
    response_data = {
        "email": email,
        "phone_number": phone_number,
        "course_id": course_id,
        "program_uuid": program_uuid,
        "course_start_date": course_start_date,
        "program_start_date": program_start_date
    }

    # Remove None values
    response_data = {k: v for k, v in response_data.items() if v is not None}

    return JsonResponse(response_data, status=status.HTTP_200_OK)




class ContactAndCountryUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        try:
            user_id = (int)(request.data['user_id'])
            phone_number = request.data.get('mobile_number')
            country_code = request.data.get('country')
            loggng.info(country_code)

            if not user_id:
                return Response({"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)

            if user_id:
                try:
                    user_profile = UserProfile.objects.get(user_id=user_id)
                except UserProfile.DoesNotExist:
                    user_profile = UserProfile(user_id=user_id)
            # elif email:
            #     try:
            #         user_profile = UserProfile.objects.get(email=email)
            #     except UserProfile.DoesNotExist:
            #         user_profile = UserProfile(email=email)

            if phone_number:
                user_profile.phone_number = phone_number

            if country_code:
                user_profile.country = country_code

            user_profile.save()

            return Response({"message": "User profile updated successfully"}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)